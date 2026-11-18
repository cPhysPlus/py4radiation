#!/usr/bin/env python3

"""
Execute Cloudy calculations and process their numerical outputs.

This module provides the worker routines used by pyCIAO for
heating/cooling and ionisation-fraction calculations.

Cloudy calculations may be distributed using Python
multiprocessing or MPI.

Failed temperature calculations are recorded and counted,
while numerical placeholders preserve the expected
dimensions of the output tables.
"""

import logging
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Final, TypedDict

import numpy as np
from numpy.typing import NDArray

from .parser import Config
from .tasks import TaskDef


class TaskResult(TypedDict):
    """
        Describe the result of one Cloudy execution task.

        Attributes
        ----------
        run_index : int
            Number identifying the attempted calculation.
        status : str
            Execution status, either 'success' or 'failed'.
            A task fails if one or more temperature calculations
            fail or cannot be processed.
        error : str or None
            Description of the failure, or None if the task succeeds.
        """

    run_index: int
    status: str
    error: str | None


WORKER_CONFIG: Config | None = None

ATOMIC_MASSES: Final[NDArray[np.float64]] = np.array(
    [
        1.00794,
        4.002602,
        6.941,
        9.012182,
        10.811,
        12.0107,
        14.0067,
        15.9994,
        18.9984032,
        20.1797,
        22.989770,
        24.3050,
        26.981538,
        28.0855,
        30.973761,
        32.065,
        35.453,
        39.948,
        39.0983,
        40.078,
        44.955910,
        47.867,
        50.9415,
        51.9961,
        54.938049,
        55.845,
        58.933200,
        58.6934,
        63.546,
        65.409,
    ]
)

ELEMENT_DATA: Final[dict[str, Any]] = {
    "atomicNumber": {
        "H": 1,
        "He": 2,
        "Li": 3,
        "Be": 4,
        "B": 5,
        "C": 6,
        "N": 7,
        "O": 8,
        "F": 9,
        "Ne": 10,
        "Na": 11,
        "Mg": 12,
        "Al": 13,
        "Si": 14,
        "P": 15,
        "S": 16,
        "Cl": 17,
        "Ar": 18,
        "K": 19,
        "Ca": 20,
        "Sc": 21,
        "Ti": 22,
        "V": 23,
        "Cr": 24,
        "Mn": 25,
        "Fe": 26,
        "Co": 27,
        "Ni": 28,
        "Cu": 29,
        "Zn": 30,
    },
    "atomicName": {
        "H": "Hydrogen",
        "He": "Helium",
        "Li": "Lithium",
        "Be": "Beryllium",
        "B": "Boron",
        "C": "Carbon",
        "N": "Nitrogen",
        "O": "Oxygen",
        "F": "Fluorine",
        "Ne": "Neon",
        "Na": "Sodium",
        "Mg": "Magnesium",
        "Al": "Aluminium",
        "Si": "Silicon",
        "P": "Phosphorus",
        "S": "Sulphur",
        "Cl": "Chlorine",
        "Ar": "Argon",
        "K": "Potassium",
        "Ca": "Calcium",
        "Sc": "Scandium",
        "Ti": "Titanium",
        "V": "Vanadium",
        "Cr": "Chromium",
        "Mn": "Manganese",
        "Fe": "Iron",
        "Co": "Cobalt",
        "Ni": "Nickel",
        "Cu": "Copper",
        "Zn": "Zinc",
    },
}


class CloudyExecutionError(RuntimeError):
    """
    Represent a failure to launch a Cloudy subprocess.
    """


def setup_worker_logging(rank: int | None = None) -> None:
    """
    Configure logging for an MPI rank or multiprocessing worker.

    Parameters
    ----------
    rank : int or None, optional
        MPI rank to include in log messages.
        If None, identify the worker using its process ID.
    """
    if rank is not None:
        log_fmt = f"[Rank-{rank}] %(levelname)s - %(message)s"
    else:
        log_fmt = "[Worker-%(process)d] %(levelname)s - %(message)s"

    logging.basicConfig(
        level=logging.INFO,
        format=log_fmt,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def initialise_worker(
    config: Config,
    rank: int | None = None,
    configure_logging: bool = True,
) -> None:
    """
    Initialise a worker with the shared Cloudy configuration.

    The configuration is stored for subsequent calls to execute_task().

    Parameters
    ----------
    config : Config
        Parsed and validated pyCIAO configuration.
    rank : int or None, optional
        MPI rank used to identify the worker in log messages.
    configure_logging : bool, optional
        Whether to configure worker-specific logging.
        Defaults to True.

        If False, retain the existing logging configuration,
        particularly the main log-file handler on MPI rank zero.
    """
    global WORKER_CONFIG
    WORKER_CONFIG = config

    if configure_logging:
        setup_worker_logging(rank)

def execute_task(task: TaskDef) -> TaskResult:
    """
    Execute one Cloudy task and report its completion status.

    The selected calculation mode determines whether heating/cooling
    or ionisation-fraction maps are generated.

    A task is considered successful only when every temperature
    calculation completes and its output is processed successfully.

    If one or more temperature calculations fail, the task is
    reported as failed even when placeholder rows have been
    written to preserve the output dimensions.

    Unexpected exceptions are recorded as failed results.

    Parameters
    ----------
    task : TaskDef
        Dictionary containing the run number, execution mode,
        output-file stem and Cloudy commands.

    Returns
    -------
    TaskResult
        Dictionary containing:
        - run_index : int
        - status : 'success' or 'failed'
        - error : str or None
    """
    global WORKER_CONFIG

    if WORKER_CONFIG is None:
        return {
            "run_index": task.get("run_index", -1),
            "status": "failed",
            "error": "Worker not initialised",
        }

    run_index = task["run_index"]
    run_mode = int(task["run_mode"])

    start_time = time.time()
    logging.info(f"Run {run_index} STARTED.")

    try:
        if run_mode == 1:
            n_failed = heatingcooling(task, WORKER_CONFIG)
        elif run_mode == 3:
            n_failed = ionfractions(task, WORKER_CONFIG)
        else:
            raise ValueError(f"Unsupported run mode: {run_mode}.")

        elapsed = time.time() - start_time

        if n_failed > 0:
            error = (
                f"{n_failed} temperature calculation(s) failed "
                f"or could not be processed."
            )
            logging.error(f"Run {run_index} FAILED in {elapsed:.2f} s: {error}")

            return {"run_index": run_index, "status": "failed", "error": error}

        logging.info(f"Run {run_index} FINISHED in {elapsed:.2f} s.")

        return {"run_index": run_index, "status": "success", "error": None}

    except Exception as e:
        logging.error(f"Run {run_index} FAILED", exc_info=True)

        return {"run_index": run_index, "status": "failed", "error": str(e)}


def run_subprocess(
    commands: list[str], infile: Path, outfile: Path, cloudy_exe: str
) -> bool:
    """
    Execute one Cloudy subprocess.

    The supplied commands are written to a Cloudy input file.
    The Cloudy executable is then launched with that file
    as its standard input.

    Successful execution requires both a zero return code and
    the expected 'Cloudy exited OK' completion message.

    Parameters
    ----------
    commands : list[str]
        Cloudy instructions to write to the input file.
    infile : Path
        Path to the temporary Cloudy input file.
    outfile : Path
        Path to the Cloudy standard-output file.
    cloudy_exe : str
        Path to the Cloudy executable.

    Returns
    -------
    bool
        True if Cloudy failed or crashed.
        False if Cloudy completed successfully.

    Raises
    ------
    OSError
        If an input/output operation fails or the Cloudy
        executable cannot be found.
    CloudyExecutionError
        If launching the subprocess raises a subprocess error.

    Notes
    -----
    The return value indicates failure rather than success.
    """
    try:
        with open(infile, "w") as f:
            f.writelines(f"{cmd}\n" for cmd in commands)
    except OSError as e:
        raise IOError(f"Failed to write input file {infile}.") from e

    try:
        with open(outfile, "w") as f_out, open(infile, "r") as f_in:
            result = subprocess.run(
                [cloudy_exe],
                stdin=f_in,
                stdout=f_out,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

    except FileNotFoundError:
        raise FileNotFoundError(f"Cloudy executable not found at: {cloudy_exe}.")
    except subprocess.SubprocessError as e:
        raise CloudyExecutionError(f"Subprocess failed to launch: {e}.") from e
    except OSError as e:
        raise OSError(f"IO error during subprocess execution: {e}.") from e

    crashed = True
    try:
        if outfile.exists():
            with open(outfile, "r") as f:
                lines = f.readlines()
                if lines and any("Cloudy exited OK" in line for line in lines[-10:]):
                    crashed = False
    except OSError:
        pass

    if result.returncode != 0 or crashed:
        logging.warning(f"Cloudy reported an error or crashed for {infile}.")
        if result.stderr:
            logging.warning(f"Cloudy stderr: {result.stderr.strip()}.")
        return True

    return False


def _get_temperature_loop(config: Config) -> list[float]:
    """
    Generate the temperature grid for a Cloudy calculation.

    Temperatures are logarithmically spaced using either the
    requested number of samples or a logarithmic temperature step.

    Parameters
    ----------
    config : Config
        Configuration containing the minimum and maximum
        temperatures and the sampling parameters.

    Returns
    -------
    list[float]
        Temperature values in kelvin.

    Raises
    ------
    ValueError
        If temperature limits or sampling parameters are invalid.
    """
    par = config.params
    try:
        tmin = float(par["coolingMapTmin"])
        tmax = float(par["coolingMapTmax"])

        if not (np.isfinite(tmin) and np.isfinite(tmax)):
            raise ValueError("Temperature limits must be finite.")

        if tmin <= 0 or tmax < tmin:
            raise ValueError("Temperature limits must be positive and increasing.")

        tpts = par.get("coolingMapTpoints")
        tlog = par.get("coolingMapdLogT")

        if tpts and tlog:
            raise ValueError("coolingMapTpoints and coolingMapdLogT cannot both be set")

        temperatures: list[float] = []

        if tpts:
            points = int(tpts)
            if points == 1:
                return [tmin]
            logtmin = np.log10(tmin)
            logtmax = np.log10(tmax)
            dlogT = (logtmax - logtmin) / (points - 1)
            for i in range(points):
                temperatures.append(10 ** (logtmin + i * dlogT))

        elif tlog:
            step = float(tlog)

            if not np.isfinite(step) or step <= 0:
                raise ValueError("coolingMapdLogT must be positive and finite")

            current_t = tmin
            while current_t <= tmax * (1 + 1e-9):
                temperatures.append(current_t)
                current_t *= 10**step

        else:
            raise ValueError("Must specify either coolingMapTpoints or coolingMapdLogT")

        return temperatures

    except Exception as e:
        raise ValueError(f"Error initialising temperature loop: {e}") from e


def _get_loops(task: TaskDef, config: Config) -> list[str]:
    """
    Extract the loop-specific Cloudy commands from a task.

    Parameters
    ----------
    task : TaskDef
        Cloudy task containing the specialised commands.
    config : Config
        Configuration defining the recognised loop commands.

    Returns
    -------
    list[str]
        Loop-specific Cloudy commands for the selected task.
    """
    loops = []
    loop_keys = [
        item["command"].split()[0] for item in config.loops_cmd if "command" in item
    ]

    for cmd in task["base_commands"]:
        for key in loop_keys:
            if cmd.startswith(key):
                loops.append(cmd)
                break
    return loops


def _get_physical_conditions(filepath: Path) -> tuple[float, float]:
    """
    Extract hydrogen and electron number densities.

    The values are obtained from the Cloudy physical-conditions
    output file.

    Parameters
    ----------
    filepath : Path
        Path to the Cloudy physical-conditions file.

    Returns
    -------
    tuple[float, float]
        Hydrogen number density and electron number density,
        respectively, in cm^-3.

        Returns (0.0, 0.0) if the file cannot be read or parsed.
    """
    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
            if not lines:
                return 0.0, 0.0

        last_line = lines[-1].strip()
        parts = last_line.split("\t")

        if len(parts) >= 4:
            hden = float(parts[2])
            eden = float(parts[3])
            return hden, eden
        return 0.0, 0.0
    except (ValueError, IndexError, OSError):
        return 0.0, 0.0


def _get_cooling(filepath: Path) -> tuple[float, float]:
    """
    Extract heating and cooling rates from Cloudy output.

    The method reads the final valid data row of the Cloudy
    cooling file and retrieves the heating and cooling rates.

    Parameters
    ----------
    filepath : Path
        Path to the Cloudy cooling output file.

    Returns
    -------
    tuple[float, float]
        Heating and cooling rates before density normalisation.

    Raises
    ------
    ValueError
        If no valid numerical data can be extracted.
    """
    try:
        with open(filepath, "r") as f:
            lines = f.readlines()

        for line in reversed(lines):
            if not line.lstrip().startswith("#"):
                parts = line.split("\t")
                if len(parts) >= 4:
                    return float(parts[2]), float(parts[3])
        raise ValueError("No valid data line found.")
    except Exception as e:
        raise ValueError(f"Failed to parse cooling data from {filepath}.") from e


def _get_mmw(abunfile: Path, ionsfile: Path) -> float:
    """
    Calculate the mean molecular weight from Cloudy outputs.

    The calculation uses elemental abundances and the mean
    ionisation fractions to estimate the mass per particle.

    Parameters
    ----------
    abunfile : Path
        Path to the Cloudy elemental-abundance output file.
    ionsfile : Path
        Path to the Cloudy mean-ionisation output file.

    Returns
    -------
    float
        Mean molecular weight in atomic mass units.

        Returns 0.0 if the required data cannot be read
        or processed.
    """
    rel_abund = []
    try:
        with open(abunfile, "r") as f:
            lines = [l for l in f if l.strip() and not l.startswith("#")]

            if lines:
                vals = [float(x) for x in lines[-1].split()]
                if vals:
                    hval = vals[0]
                    rel_abund = [10 ** (x - hval) for x in vals]

    except OSError:
        return 0.0

    if not rel_abund:
        return 0.0

    num_re = re.compile(r"[+-]?\d+\.\d+(?:[Ee][+-]?\d+)?")

    total_mass = 0.0
    total_particles = 0.0
    idx = 0
    procs = False

    try:
        with open(ionsfile, "r") as f:
            lines = f.readlines()

        if not lines:
            raise OSError("Failed to parse ionisation file.")

        for line in lines:
            if "Hydrogen" in line:
                procs = True
            if not procs:
                continue

            if re.match(r"^\s*[a-zA-Z]", line):
                logfracs = [float(x) for x in num_re.findall(line)]

                if idx < len(ATOMIC_MASSES) and idx < len(rel_abund):
                    z = idx + 1
                    fracs = logfracs[: z + 1]

                    abund = rel_abund[idx]
                    mass = ATOMIC_MASSES[idx]
                    total_mass += abund * mass

                    for w, logfrac in enumerate(fracs):
                        linfrac = 10**logfrac
                        total_particles += abund * linfrac * (w + 1)

                    idx += 1

        if total_particles == 0.0:
            return 0.0

        return total_mass / total_particles

    except Exception:
        return 0.0


def _get_ion_fraction(ionsfile: Path, elements: list[str]) -> dict[str, list[float]]:
    """
    Extract ionisation fractions for selected elements.

    The method reads the mean-ionisation output produced by
    Cloudy and extracts the logarithmic ionisation fractions
    for the requested chemical elements.

    Missing ionisation stages within a recognised element
    are padded using the numerical value -30.0.

    Parameters
    ----------
    ionsfile : Path
        Path to the Cloudy mean-ionisation output file.
    elements : list[str]
        Chemical element symbols to extract.

    Returns
    -------
    dict[str, list[float]]
        Dictionary mapping each requested element to its
        logarithmic ionisation fractions.

        Completely absent elements may have empty lists.

    Raises
    ------
    OSError
        If the ionisation output cannot be read or parsed.
    """

    name2symbol = {v: k for k, v in ELEMENT_DATA["atomicName"].items()}
    atomic_numbers = ELEMENT_DATA["atomicNumber"]
    elements_data: dict[str, list[float]] = {el: [] for el in elements}

    num_re = re.compile(r"[+-]?\d+\.\d+(?:[Ee][+-]?\d+)?")

    try:
        with open(ionsfile, "r") as f:
            lines = f.readlines()

        idx = -1
        for i, line in enumerate(lines):
            if "Hydrogen" in line:
                idx = i

        if idx == -1:
            raise ValueError("No ionisation data block found")

        for line in lines[idx:]:
            line = line.strip()
            if not line:
                continue

            match = re.match(r"^\s*([a-zA-Z]+)", line)
            if match:
                element_name = match.group(1)
                symbol = name2symbol.get(element_name)

                if symbol in elements_data:
                    vals = num_re.findall(line)
                    logfracs = [float(x) for x in vals]

                    if symbol in atomic_numbers:
                        z = atomic_numbers[symbol]
                        expected_ions = z + 1

                        if len(logfracs) < expected_ions:
                            padding = [-30.0] * (expected_ions - len(logfracs))
                            logfracs.extend(padding)

                        elements_data[symbol] = logfracs[:expected_ions]

        return elements_data

    except Exception as e:
        raise OSError(f"Failed to parse ion fractions from {ionsfile}: {e}") from e


def heatingcooling(task: TaskDef, config: Config) -> int:
    """
    Calculate a radiative heating/cooling map for one task.

    This routine executes Cloudy over the configured temperature
    grid and extracts the corresponding heating and cooling rates
    and mean molecular weights.

    The output contains four columns:

        1. Temperature [K].
        2. Heating coefficient.
        3. Cooling coefficient.
        4. Mean molecular weight [amu].

    The heating and cooling rates are normalised according
    to coolingScaleFactor:

        1 : divide by n_H**2.
        2 : divide by n_H*n_e.

    For coolingScaleFactor=1, the resulting coefficients have
    units of erg cm^3 s^-1.

    When a temperature calculation fails, zero-valued physical
    quantities are written to preserve the table dimensions.
    The failure is also counted.

    Parameters
    ----------
    task : TaskDef
        Cloudy task containing the run number, output-file
        stem and base commands.
    config : Config
        Configuration containing the Cloudy executable,
        physical parameters and temperature grid.

    Returns
    -------
    int
        Number of temperature calculations that failed
        or could not be processed.
    """
    key_name = task["key_name"]
    datfile_path = Path(f"{key_name}.dat")

    temp_suffix = ".temp"
    temp_infile = Path(f"{key_name}.cloudyIn{temp_suffix}")
    temp_outfile = Path(f"{key_name}.cloudyOut{temp_suffix}")

    temp_heatfile = Path(f"{key_name}.heating{temp_suffix}")
    temp_coolfile = Path(f"{key_name}.cooling{temp_suffix}")

    temp_abunfile = Path(f"{key_name}.abundance{temp_suffix}")
    temp_ionsfile = Path(f"{key_name}.ionization{temp_suffix}")
    temp_physfile = Path(f"{key_name}.physical{temp_suffix}")

    temp_toclean = [
        temp_infile,
        temp_outfile,
        temp_heatfile,
        temp_coolfile,
        temp_abunfile,
        temp_ionsfile,
        temp_physfile,
    ]

    loop_vals = _get_loops(task, config)

    with open(datfile_path, "w") as f:
        f.write(f"# {time.asctime()}\n#\n")
        f.write("# Cooling Map File\n#\n")
        f.write("# Loop values:\n")
        f.writelines(f"# {val}\n" for val in loop_vals)
        f.write("#\n")
        f.write("# Data Columns:\n")
        f.write("# 1: Te [K]\n")
        f.write("# 2: Heating [erg s^-1 cm^3]\n")
        f.write("# 3: Cooling [erg s^-1 cm^3]\n")
        f.write("# 4: Mean Molecular Weight [amu]\n#\n")
        f.write("#Te\t\tHeating\t\tCooling\t\tMMW\n")

    temperatures = _get_temperature_loop(config)
    scale_factor = int(config.params.get("coolingScaleFactor", 1))

    n_failed = 0

    for temp in temperatures:
        commands = list(task["base_commands"])

        commands.append(f"constant temperature {temp:.6e} K linear")
        commands.append(f'punch last cooling file = "{temp_coolfile}"')
        commands.append(f'punch last heating file = "{temp_heatfile}"')
        commands.append(f'punch last abundance file = "{temp_abunfile}"')
        commands.append(f'punch last ionization means file = "{temp_ionsfile}"')
        commands.append(f'punch last physical conditions file = "{temp_physfile}"')

        crashed = run_subprocess(
            commands, temp_infile, temp_outfile, str(config.params["cloudyExe"])
        )

        heating, cooling, mmw = 0.0, 0.0, 0.0

        if crashed:
            n_failed += 1

            logging.warning(
                f"Run {task['run_index']}, T={temp:.2e} K: Cloudy crashed. Writing zeros ... "
            )

        else:
            try:
                hden, eden = _get_physical_conditions(temp_physfile)

                if not np.isfinite(hden) or hden <= 0:
                    raise ValueError("Invalid hydrogen density in Cloudy output.")

                heating, cooling = _get_cooling(temp_coolfile)

                if scale_factor == 1:
                    factor = hden * hden
                elif scale_factor == 2:
                    if not np.isfinite(eden) or eden <= 0:
                        raise ValueError("Invalid electron density in Cloudy output.")

                    factor = hden * eden
                else:
                    raise ValueError(f"Invalid coolingScaleFactor: {scale_factor}")

                if not np.isfinite(factor) or factor <= 0:
                    raise ValueError("Invalid density normalisation factor.")

                heating /= factor
                cooling /= factor

                mmw = _get_mmw(temp_abunfile, temp_ionsfile)

                if not np.isfinite(mmw) or mmw <= 0:
                    raise ValueError("Invalid mean molecular weight.")

            except Exception as e:
                n_failed += 1

                logging.error(
                    f"Run {task['run_index']}, T={temp:.2e} K: Post-processing failed: {e}"
                )

                heating, cooling, mmw = 0.0, 0.0, 0.0

        with open(datfile_path, "a") as f:
            f.write(f"{temp:.6e}\t{heating:.6e}\t{cooling:.6e}\t{mmw:.6f}\n")

    for f in temp_toclean:
        f.unlink(missing_ok=True)

    return n_failed

def ionfractions(task: TaskDef, config: Config) -> int:
    """
Calculate ionisation-fraction maps for one Cloudy task.

    The method executes Cloudy across the configured temperature
    grid and extracts logarithmic ionisation fractions for
    the requested elements.

    A separate output file is generated for each element.

    Each file contains:

        1. Logarithmic temperature, log10(T/K).
        2. Logarithmic ionisation fractions for each ion stage.

    Failed calculations are represented by -30.0 placeholders
    to preserve the expected number of ionisation stages.

    A temperature calculation is counted as failed if Cloudy
    crashes or the ionisation data cannot be processed correctly.

    Parameters
    ----------
    task : TaskDef
        Cloudy task containing the run number, output-file
        stem and base commands.
    config : Config
        Configuration containing the Cloudy executable,
        selected chemical elements and temperature grid.

    Returns
    -------
    int
        Number of temperature calculations that failed
        or could not be processed.
    """
    key_name = task["key_name"]

    elements = str(config.params.get("ionFractionElements", ""))
    elements = elements.split()

    if not elements:
        raise ValueError("ionFractionElements not specified")

    temp_suffix = ".temp"
    temp_infile = Path(f"{key_name}.cloudyIn{temp_suffix}")
    temp_outfile = Path(f"{key_name}.cloudyOut{temp_suffix}")
    temp_ionsfile = Path(f"{key_name}.ionization{temp_suffix}")

    temp_toclean = [temp_infile, temp_outfile, temp_ionsfile]

    loop_vals = _get_loops(task, config)

    dat_files = {}
    for el in elements:
        if el not in ELEMENT_DATA["atomicNumber"]:
            logging.warning(f'Run {task["run_index"]}: Skipping unknown element "{el}"')
            continue

        datfile_path = Path(f"{key_name}_{el}.dat")
        dat_files[el] = datfile_path

        with open(datfile_path, "w") as f:
            f.write(f"# {time.asctime()}\n#\n")
            f.write(
                f"# Element: {ELEMENT_DATA['atomicName'].get(el, el)} Ion Fraction File\n#\n"
            )
            f.write("# Loop values:\n")
            f.writelines(f"# {val}\n" for val in loop_vals)
            f.write("#\n")
            f.write("# Data Columns:\n")
            f.write("# log(Te [K])\n")
            f.write("# log(Ion Fractions)\n#\n")

            num_ions = ELEMENT_DATA["atomicNumber"][el] + 1
            ion_cols = [f"{i + 1}" for i in range(num_ions)]
            f.write("#Te\t" + "\t".join(f"{col}" for col in ion_cols) + "\n")

    temperatures = _get_temperature_loop(config)
    n_failed = 0

    for temp in temperatures:
        commands = list(task["base_commands"])

        commands.append(f"constant temperature {temp:.6e} K linear")
        commands.append(f'punch last ionization means file = "{temp_ionsfile}"')

        crashed = run_subprocess(
            commands, temp_infile, temp_outfile, str(config.params["cloudyExe"])
        )

        all_ion_fractions = {}
        failed = crashed

        if crashed:
            logging.warning(f"Run {task['run_index']}, T={temp:.2e} K: Cloudy crashed")
            for el in dat_files:
                num_ions = ELEMENT_DATA["atomicNumber"][el] + 1
                all_ion_fractions[el] = [-30.0] * num_ions

        else:
            try:
                all_ion_fractions = _get_ion_fraction(temp_ionsfile, elements)
            except Exception as e:
                failed = True

                logging.error(
                    f"Run {task['run_index']}, T={temp:.2e} K: Ion fraction parsing failed: {e}"
                )
                for el in dat_files:
                    num_ions = ELEMENT_DATA["atomicNumber"][el] + 1
                    all_ion_fractions[el] = [-30.0] * num_ions

        log_temp = np.log10(temp)
        for el, f_path in dat_files.items():
            fractions = all_ion_fractions.get(el, [])
            expected = ELEMENT_DATA["atomicNumber"][el] + 1

            if len(fractions) != expected:
                failed = True

                logging.error(
                    f"Run {task['run_index']}, T={temp:.2e} K: "
                    f"Incomplete ionisation data for {el}. "
                    f"Expected {expected} fractions, "
                    f"received {len(fractions)}."
                )

                all_ion_fractions[el] = [-30.0] * expected

            with open(f_path, "a") as f:
                fracs = [f"{frac:.3f}" for frac in fractions]
                f.write(f"{log_temp:.3f}\t" + "\t".join(fracs) + "\n")

        if failed:
            n_failed +=1

    for f in temp_toclean:
        f.unlink(missing_ok=True)

    return n_failed
