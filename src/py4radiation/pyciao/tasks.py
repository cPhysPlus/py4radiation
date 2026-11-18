#!/usr/bin/env python3

"""
Generate Cloudy execution tasks from parsed pyCIAO loops.
"""

import itertools
import logging
from collections.abc import Iterator
from typing import TypedDict, cast

import numpy as np
from numpy.typing import NDArray

from .parser import Config


class TaskDef(TypedDict):
    """
    Describe one Cloudy calculation for a worker process.

    Attributes
    ----------
    run_index : int
        Number identifying the Cloudy run.
    key_name : str
        Output-file stem, including its destination directory.
    base_commands : list[str]
        Constant and loop-specific Cloudy instructions.
    run_mode : int
        Cloudy execution mode: 1 for heating/cooling
        or 3 for ionisation fractions.
    """
    run_index: int
    key_name: str
    base_commands: list[str]
    run_mode: int


class TaskManager:
    """
    Generate Cloudy execution tasks based on the parsed configuration.

    The class combines all configured loop values using a
    Cartesian product and creates one task for each combination.

    The task ordering is consistent with the ordered parameter
    combinations recorded in the master pyCIAO .run file.

    Parameters
    ----------
    config : Config
        Parsed pyCIAO configuration.

    Attributes
    ----------
    config : Config
        Configuration used to generate the tasks.
    start_idx : int
        Initial run number obtained from runStartIndex.
        Defaults to 1.
    """

    def __init__(self, config: Config) -> None:
        """
        Store the configuration and determine the initial run number.
        """
        self.config = config
        self.start_idx = int(config.params.get("runStartIndex", 1))

    def _create_task(self, run_idx: int, loops_cmd: list[str]) -> TaskDef:
        """
        Create a worker task for one combination of loop values.

        Parameters
        ----------
        run_idx : int
            Run number assigned to the calculation.
        loops_cmd : list[str]
            Specific list of loop commands for this run.

        Returns
        -------
        TaskDef
            Dictionary containing the run number, output-file stem,
            Cloudy commands and calculation mode.
        """
        outdir = self.config.params.get("outputDir", "")
        prefix = self.config.params.get("outputFilePrefix", "ciaorun")

        key_name = f"{outdir}{prefix}_run{run_idx}"

        final_cmd = list(self.config.const_cmd)
        final_cmd.extend(loops_cmd)

        run: TaskDef = {
            "run_index": run_idx,
            "key_name": key_name,
            "base_commands": final_cmd,
            "run_mode": int(self.config.params["cloudyRunMode"]),
        }

        return run

    def _format_cmd(
        self, template: str, value: float | str | NDArray[np.float64]
    ) -> str:
        """
        Insert a loop value into a Cloudy command template.

        If the template contains '*', replace it with the value.
        Otherwise, append the value to the template.

        Parameters
        ----------
        template : str
            Command template.
        value : float | str | NDArray[np.float64]
            Value to insert into the command.

        Returns
        -------
        str
            Formatted command string.
        """
        val = str(value)
        if "*" in template:
            return template.replace("*", val)
        else:
            return f"{template} {val}"

    def gen_tasks(self) -> Iterator[TaskDef]:
        """
        Generate a stream of tasks by iterating over all configured loops.

        Yields
        ------
        TaskDef
            Dictionary describing one Cloudy calculation.
        """

        loop_iter = []

        for loop_item in self.config.loops_cmd:
            if loop_item["type"] == "single":
                cmd = str(loop_item["command"])
                raw_vals = loop_item["values"]

                iterable = []
                if isinstance(raw_vals, np.ndarray):
                    vals_arr = cast(NDArray[np.float64], raw_vals)
                    iterable = [(self._format_cmd(cmd, val),) for val in vals_arr]
                else:
                    iterable = [(self._format_cmd(cmd, val),) for val in raw_vals]

                loop_iter.append(iterable)

            elif loop_item["type"] == "set":
                # Future implementation.
                continue

        if not loop_iter:
            logging.info("No loop commands found. Generating a single task.")
            yield self._create_task(self.start_idx, [])
            return

        run_idx = self.start_idx

        for task_cmd in itertools.product(*loop_iter):
            loops_cmd = [item[0] for item in task_cmd]

            yield self._create_task(run_idx, loops_cmd)
            run_idx += 1
