#!/usr/bin/env python3

"""
Parse pyCIAO parameter files and Cloudy loop expressions.
"""

import logging
import re
from pathlib import Path
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

RE_FOR: Final[re.Pattern] = re.compile(
    r"\((-?\d*\.?\d*)\;(-?\d*\.?\d*)\;(-?\d*\.?\d*)\)"
)
RE_CMD: Final[re.Pattern] = re.compile(r"^loop\s+\[(.+?)\]\s+(.+)$", re.IGNORECASE)
RE_SET: Final[re.Pattern] = re.compile(r"loop\s*\{")
RE_PAR: Final[re.Pattern] = re.compile(r"^([a-zA-Z0-9_]+)\s*[=\s]\s*(.+)")


class Config:
    """
    Parse and validate configuration files for pyCIAO.

    The parser reads the configuration parameters, constant
    Cloudy commands and loop definitions from a .par file.

    The resulting configuration is used by TaskManager to
    generate individual Cloudy calculation tasks.

    Parameters
    ----------
    parfile : str or Path
        Path to the pyCIAO parameter file.

    Attributes
    ----------
    parfile : Path
        Path to the input parameter file.
    params : dict[str, Any]
        Configuration parameters and their values.
    const_cmd : list[str]
        Cloudy instructions executed in every calculation.
    loops_cmd : list[dict[str, Any]]
        Ordered loop definitions containing the command,
        values and loop type.
    modes : dict[int, str]
        Supported Cloudy execution modes.
    """

    def __init__(self, parfile: str | Path) -> None:
        """
        Initialize the Config parser.

        Parameters
        ----------
        parfile : str | Path
            Path to the input parameter file (.par).

        Raises
        ------
        FileNotFoundError
            If the provided parameter file does not exist.
        """
        self.parfile = Path(parfile)

        if not self.parfile.exists():
            raise FileNotFoundError(f"Parameter file not found: {self.parfile}.")

        self.params: dict[str, Any] = {}
        self.const_cmd: list[str] = []
        self.loops_cmd: list[dict[str, Any]] = []

        self.modes: dict[int, str] = {1: "HeatingCoolingMap", 3: "IonFractionMap"}

    def _parse_loops(self, val: str) -> NDArray[np.float64] | list[str]:
        """
        Expand a loop expression into its requested values.

        The method supports numerical ranges of the form
        (start;end;step), as well as explicitly listed values.

        Parameters
        ----------
        val : str
            Value containing loop definitions.

        Returns
        -------
        numpy.ndarray[np.float64] or list[str]
            Numpy array of values if range is detected,
            otherwise list of string values.

        Raises
        ------
        ValueError
            If the loop syntax is invalid or results in an infinite loop.
        """
        val = val.strip()

        match = RE_FOR.search(val)
        if match:
            try:
                start = float(match.group(1))
                end = float(match.group(2))
                step = float(match.group(3))
            except ValueError as err:
                raise ValueError(f"Invalid for loop parameter: {val}.") from err

            if step == 0:
                raise ValueError(f"Invalid step (0) in loop: {val}.")

            if (end - start) * step < 0:
                raise ValueError(f"Loop step points away from the endpoint: {val}.")

            return np.arange(start, end + step, step)

        return val.replace(",", " ").split()

    def _validate_config(self) -> None:
        """
        Validate parsed configuration parameters.

        Ensures required keys exist and values are within expected ranges.
        Modifies `self.params` in place to set defaults or fix paths.

        Raises
        ------
        ValueError
            If required parameters are missing or invalid.
        """
        try:
            mode = int(self.params["cloudyRunMode"])
            if mode not in self.modes:
                raise ValueError(
                    f"Unsupported cloudyRunMode: {mode}. Supported modes: {self.modes}."
                )

        except (ValueError, KeyError) as err:
            raise ValueError(
                "Invalid or missing cloudyRunMode. Must be an integer."
            ) from err

        if "cloudyExe" not in self.params:
            raise ValueError("cloudyExe must be specified in the parameter file.")

        outdir = self.params.get("outputDir", ".")
        if outdir == ".":
            logging.warning(
                "Output directory not set, defaulting to current directory."
            )
            self.params["outputDir"] = ""
        else:
            path_out = Path(outdir)
            path_out.mkdir(parents=True, exist_ok=True)
            self.params["outputDir"] = f"{path_out}/"

        if "outputFilePrefix" not in self.params:
            logging.warning('outputFilePrefix not set, defaulting to "ciaorun".')
            self.params["outputFilePrefix"] = "ciaorun"

        mode_int = int(self.params["cloudyRunMode"])

        if mode_int == 1:
            if not all(k in self.params for k in ["coolingMapTmin", "coolingMapTmax"]):
                raise ValueError(
                    'Heating/Cooling rates requires "coolingMapTmin" and "coolingMapTmax".'
                )

        if mode_int == 3:
            if not all(k in self.params for k in ["coolingMapTmin", "coolingMapTmax"]):
                raise ValueError(
                    'Ion Fraction maps requires "coolingMapTmin" and "coolingMapTmax".'
                )

            if "ionFractionElements" not in self.params:
                logging.warning('ionFractionElements not set, defaulting to "H C N O".')
                self.params["ionFractionElements"] = "H C N O"

    def parse(self) -> None:
        """
        Parse the parameter file and populate the configuration.

        The method separates constant Cloudy commands from
        loop definitions and general configuration parameters.

        Parsed values are subsequently validated.

        Raises
        ------
        ValueError
            If a parameter-file line is malformed or
            configuration validation fails.
        OSError
            If the parameter file cannot be read.
        """
        logging.info(f"Parsing parameter file: {self.parfile}.")

        try:
            with open(self.parfile, "r") as f:
                lines = f.readlines()

        except IOError as e:
            raise IOError(f"Failed to read parameter file {self.parfile}: {e}.")

        for n, line in enumerate(lines, 1):
            rline = line.strip().split("#", 1)[0].strip()

            if not rline:
                continue

            low = rline.lower()

            try:
                if low.startswith("command"):
                    cmd = rline.split(maxsplit=1)
                    if len(cmd) > 1:
                        self.const_cmd.append(cmd[1])
                    else:
                        logging.warning(f"Line {n}: Empty command ignored.")

                elif low.startswith("loop"):
                    match = RE_CMD.search(rline)
                    if not match:
                        raise ValueError(f"Invalid loop syntax: {line}.")

                    cmd = match.group(1).strip()
                    val = match.group(2).strip()
                    val = self._parse_loops(val)

                    self.loops_cmd.append(
                        {"type": "single", "command": cmd, "values": val}
                    )
                else:
                    match = RE_PAR.match(rline)
                    if match:
                        key = match.group(1).strip()
                        val = match.group(2).strip()
                        self.params[key] = val
                    else:
                        logging.debug(f"Line {n}: Unrecognized format, skipping: {rline}")
                        continue
            except Exception as e:
                raise ValueError(f"Error parsing line {n}: {rline!r}") from e

        self._validate_config()
        logging.info("Configuration parsed succesfully.")
