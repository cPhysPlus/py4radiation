#!/usr/bin/env python3

"""
Provide the command-line and parallel-execution interface for pyCIAO.

Cloudy calculations are executed using Python multiprocessing
or MPI when multiple MPI ranks are available.

The module handles configuration parsing, task distribution,
execution-result collection and final run reporting.
"""

import argparse
import itertools
import logging
import multiprocessing
import sys
import time
from pathlib import Path

MPI_AVAILABLE = False
try:
    from mpi4py import MPI

    MPI_AVAILABLE = True
except ImportError:
    pass

from .parser import Config
from .runner import TaskResult, execute_task, initialise_worker
from .tasks import TaskDef, TaskManager


def setup_main_logging(outdir: str, prefix: str) -> None:
    """
    Configure logging for the main pyCIAO process.

    Log messages are written to the main run log file and
    standard output.

    Parameters
    ----------
    outdir : str
        Output-directory prefix defined by the configuration.
    prefix : str
        Prefix used to construct the log filename.
    """
    logfile = f"{prefix}.log"
    if outdir:
        logfile = f"{outdir}{logfile}"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(logfile, mode="w"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    logging.info(f"Log file initialised at {logfile}.")


def write_runfile(config: Config) -> None:
    """
    Write the master pyCIAO .run file.

    The file records constant Cloudy commands, ordered loop
    definitions and the parameter combinations associated
    with the numbered Cloudy runs.

    The tabular section is used by IonTables and
    HeatingCoolingTables to associate individual output
    maps with their corresponding physical parameters.

    The format and ordering must remain consistent with
    the task-generation procedure.

    Parameters
    ----------
    config : Config
        Parsed pyCIAO configuration containing the constant
        commands and loop definitions.
    """
    par = config.params

    outdir = str(par.get("outputDir", ""))
    prefix = str(par.get("outputFilePrefix", "ciaorun"))

    runfile = f"{outdir}{prefix}.run"
    logging.info(f"Writing run file: {runfile}.")

    try:
        with open(runfile, "w") as f:
            f.write(f"# Run started {time.asctime()}\n#\n")
            f.write(f"# cloudyRunMode = {par.get('cloudyRunMode')}\n")
            f.write(f"# outputFilePrefix = {prefix}\n")
            f.write(f"# outputDir = {outdir}\n#\n")

            f.write("# Commands to be executed everytime:\n")
            f.writelines(f"# {cmd}\n" for cmd in config.const_cmd)

            f.write("#\n# Loop commands and values:\n")
            headers = ["#run"]

            for item in config.loops_cmd:
                if item["type"] == "single":
                    cmd_name = item["command"].replace("\n", " ")
                    f.write(
                        f"# {cmd_name}: {' '.join(str(val) for val in item['values'])}\n"
                    )
                    headers.append(cmd_name)

                elif item["type"] == "set":
                    # Future implementation.
                    continue

            f.write("#\n")
            f.write("\t".join(headers) + "\n")

            loop_items = [item for item in config.loops_cmd if item["type"] == "single"]

            loop_values = [item["values"] for item in loop_items]

            if loop_values:
                for idx, values in enumerate(
                    itertools.product(*loop_values),
                    start=1,
                ):
                    row = [str(idx), *(str(value) for value in values)]
                    f.write("\t".join(row) + "\n")
            else:
                f.write("1\n")
    except OSError as e:
        logging.error(f"Failed to write runfile {runfile}: {e}.")


def run_mpi(config: Config | None, tasks: list[TaskDef] | None) -> list[TaskResult]:
    """
    Execute Cloudy tasks using MPI.

    The configuration and task list are broadcast from rank
    zero to the remaining MPI ranks.

    Each rank executes a subset of the tasks, and the resulting
    execution summaries are gathered by rank zero.

    Parameters
    ----------
    config : Config or None
        Parsed execution configuration supplied by rank zero.
    tasks : list[TaskDef] or None
        Numbered Cloudy tasks supplied by rank zero.

    Returns
    -------
    list[TaskResult]
        Combined task results on rank zero.
        An empty list is returned on the other ranks.

    Raises
    ------
    RuntimeError
        If the MPI initialisation data are not received.
    """
    COMM = MPI.COMM_WORLD
    RANK = COMM.Get_rank()
    SIZE = COMM.Get_size()

    config = COMM.bcast(config, root=0)
    tasks = COMM.bcast(tasks, root=0)

    if config is None or tasks is None:
        raise RuntimeError("MPI initialisation data was not received.")

    initialise_worker(config, rank=RANK, configure_logging=(RANK != 0))

    my_tasks = tasks[RANK::SIZE]
    local_results = [execute_task(t) for t in my_tasks]

    all_results = COMM.gather(local_results, root=0)

    final_results = []
    if RANK == 0 and all_results:
        for rlist in all_results:
            final_results.extend(rlist)

    return final_results


def run_multiprocessing(
    config: Config, tasks: list[TaskDef], nproc: int
) -> list[TaskResult]:
    """
    Execute Cloudy tasks using Python multiprocessing.

    The configuration is shared with the worker processes
    during their initialisation.

    Individual tasks are executed independently, and their
    results are collected as they become available.

    Parameters
    ----------
    config : Config
        Parsed pyCIAO execution configuration.
    tasks : list[TaskDef]
        Numbered Cloudy tasks to execute.
    nproc : int
        Number of worker processes.

    Returns
    -------
    list[TaskResult]
        Execution results in completion order.
    """
    logging.info(f"Starting multiprocessing pool with {nproc} processes.")

    with multiprocessing.Pool(
        processes=nproc, initializer=initialise_worker, initargs=(config,)
    ) as pool:
        results_iter = pool.imap_unordered(execute_task, tasks)

        final_results = []
        for i, result in enumerate(results_iter, start=1):
            final_results.append(result)
            if i % 10 == 0:
                logging.info(f"Progress: {i}/{len(tasks)} tasks completed.")

    return final_results


def main() -> None:
    """
    Run the pyCIAO command-line interface.

    The command-line interface accepts a parameter file
    and an optional number of multiprocessing workers.

    When launched with multiple MPI ranks, MPI execution
    takes precedence over Python multiprocessing.

    The main process generates the master .run file,
    collects execution results and reports the total
    numbers of successful and failed tasks.

    A non-zero process exit status is returned when
    one or more tasks fail.

    Command-line arguments
    ----------------------
    parfile : Path
        Path to the pyCIAO .par configuration file.
    --nproc : int, optional
        Number of multiprocessing workers.
        Ignored when executing with MPI.
    """
    is_mpi = False
    rank = 0

    if MPI_AVAILABLE and MPI.COMM_WORLD.Get_size() > 1:
        is_mpi = True
        rank = MPI.COMM_WORLD.Get_rank()

    config: Config | None = None
    tasks: list[TaskDef] | None = None

    args = None

    if rank == 0:
        parser = argparse.ArgumentParser(
            description="pyCIAO: Hybrid MPI/multiprocessing implementation of CIAOLoop"
        )

        parser.add_argument("parfile", type=Path, help="Path to parameter file (.par).")
        parser.add_argument(
            "--nproc",
            type=int,
            default=1,
            help="Number of processes for multiprocessing (ignored if using MPI).",
        )
        args = parser.parse_args()

        if args.nproc < 1:
            raise ValueError("--nproc must be at least 1.")

        start_time = time.time()

        try:
            config = Config(args.parfile)
            config.parse()

            par = config.params
            setup_main_logging(
                par.get("outputDir", ""), par.get("outputFilePrefix", "ciaorun")
            )

            mode_str = "MPI" if is_mpi else "Multiprocessing"
            logging.info(f"--- pyCIAO {mode_str} Run Started ---")

            task_manager = TaskManager(config)
            tasks = list(task_manager.gen_tasks())

            total_tasks = len(tasks)
            logging.info(f"Generated {total_tasks} Cloudy tasks.")

            if total_tasks == 0:
                raise ValueError("No Cloudy tasks were generated.")

            write_runfile(config)
        except Exception as e:
            logging.critical(f"Rank 0 initialisation failed: {e}", exc_info=True)
            if is_mpi:
                MPI.COMM_WORLD.Abort(1)

            sys.exit(1)

    final_results = []

    if is_mpi:
        final_results = run_mpi(config, tasks)
    else:
        if config is None or tasks is None or args is None:
            raise RuntimeError("Multiprocessing initialisation failed.")
        else:
            final_results = run_multiprocessing(config, tasks, args.nproc)

    if rank == 0:
        final_results.sort(key=lambda x: x["run_index"])

        success = sum(1 for r in final_results if r["status"] == "success")
        fail = sum(1 for r in final_results if r["status"] == "failed")

        for res in final_results:
            if res["status"] == "failed":
                logging.error(f"Run {res['run_index']} FAILED: {res.get('error')}")

        end_time = time.time()

        logging.info("--- Run Finished ---")
        logging.info(f"Total tasks: {len(tasks) if tasks is not None else ''}")
        logging.info(f"Successful:  {success}")
        logging.info(f"Failed:      {fail}")
        logging.info(f"Total execution time: {end_time - start_time:.2f} seconds")

        print("--------------------------------------------------")
        print(f"All Runs Finished at {time.asctime()}")
        print("--------------------------------------------------")

        if fail > 0:
            logging.error(f"puCIAO finished with {fail} failed task(s).")
            sys.exit(1)


if __name__ == "__main__":
    main()
