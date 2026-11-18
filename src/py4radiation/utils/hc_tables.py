#!/usr/bin/env python3

"""
PRocess radiative heating and cooling tables for HD/MHD codes.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoopColumn:
    """
    Describe a parameter column from a pyCIAO .run file.

    Parameters
    ----------
    command : str
        Cloudy loop-command name to identify, such as 'hden'.
    output_header : str
        Column heading in the generated heating/cooling table.
    input_scale : {'linear', 'log10'}, optional
        Interpretation of the values recorded in the .run file.
        Defaults to 'linear'.
    factor : float, optional
        Multiplicative factor applied after converting the
        input parameter to its requested scale.
        Defaults to 1.0.
    """

    command: str
    output_header: str
    input_scale: Literal["linear", "log10"] = "linear"
    factor: float = 1.0


@dataclass(frozen=True)
class RunRecord:
    """
    Represent one numbered run from a pyCIAO .run file.

    Attributes
    ----------
    run_id : int
        Run number used to identify the corresponding Cloudy map.
    parameters : dict[str, str]
        Dictionary mapping selected loop-command headers to
        their original text values.
    """

    run_id: int
    parameters: dict[str, str]


class HeatingCoolingTables:
    """
    Combine radiative heating and cooling maps into a single table.

    This class reads the master pyCIAO .run file and the individual
    heating/cooling maps produced by Cloudy.

    For the default configuration, the output contains:

        1. Hydrogen number density [cm^-3].
        2. Temperature [K].
        3. Heating coefficient [erg cm^3 s^-1].
        4. Cooling coefficient [erg cm^3 s^-1].
        5. Mean molecular weight [amu].

    The coefficient units above assume coolingScaleFactor=1,
    corresponding to normalisation of the volumetric heating
    and cooling rates by n_H**2.

    Other coolingScaleFactor values require the appropriate
    interpretation of the resulting coefficients.

    Parameters
    ----------
    run_dir : str or Path
        Directory containing the master .run file and
        heating/cooling maps.
    run_name : str
        Common simulation identifier.
        The '.run' suffix may be supplied optionally.
    loop_columns : Sequence[LoopColumn] or None, optional
        Loop parameters to include in the final table.
        By default, the 'hden' parameter is converted from
        logarithmic to linear hydrogen number density.

    Attributes
    ----------
    run_dir : Path
        Directory containing the input files.
    run_name : str
        Common identifier for the simulation run.
    loop_columns : tuple[LoopColumn, ...]
        Selected loop parameters included in the output.
    """

    DEFAULT_LOOP_COLUMNS: tuple[LoopColumn, ...] = (
        LoopColumn(
            command="hden",
            output_header="HDEN[cm^-3]",
            input_scale="log10",
        ),
    )

    def __init__(
        self,
        run_dir: str | Path,
        run_name: str,
        loop_columns: Sequence[LoopColumn] | None = None,
    ) -> None:
        """
        Initialise the processor with the location and ID of the run.
        """
        self.run_dir = Path(run_dir).expanduser()
        self.run_name = run_name.removesuffix(".run")
        self.loop_columns = (
            self.DEFAULT_LOOP_COLUMNS if loop_columns is None else tuple(loop_columns)
        )

        if not self.run_name:
            raise ValueError("run_name must not be empty")

        commands = [column.command.strip().casefold() for column in self.loop_columns]
        if len(commands) != len(set(commands)):
            raise ValueError("loop_columns contains duplicate command names")

        for column in self.loop_columns:
            if not column.command.strip():
                raise ValueError("LoopColumn.command must not be empty")
            if column.input_scale not in {"linear", "log10"}:
                raise ValueError(
                    f"Unsupported input scale {column.input_scale!r} for "
                    f"{column.command!r}"
                )
            if not np.isfinite(column.factor):
                raise ValueError(
                    f"LoopColumn.factor must be finite for {column.command!r}"
                )

    @staticmethod
    def _split_tabfields(line: str) -> list[str]:
        """
        Split a tab-separated .run file row into individual fields.

        Spaces within Cloudy commands are preserved.

        Parameters
        ----------
        line : str
            Text row from the master .run file.

        Returns
        -------
        list[str]
            Individual fields in their original order.
        """

        return [field.strip() for field in line.rstrip("\n").split("\t")]

    @staticmethod
    def _command_word(command_header: str) -> str:
        """
        Extract the first word of a Cloudy loop-command header.

        Parameters
        ----------
        command_header : str
            Full loop-command header.

        Returns
        -------
        str
            Case-insensitive command keyword, converted to lower case.
            Returns an empty string if the header contains no words.
        """
        parts = command_header.strip().split(maxsplit=1)
        return parts[0].casefold() if parts else ""

    def _read_run_file(self, runfile: Path) -> list[RunRecord]:
        """
        Parse the tabular section of a pyCIAO .run file.

        The method identifies the table header, selects the requested
        loop parameters and constructs one record per numbered run.

        The ordering of the original run file is preserved.

        Parameters
        ----------
        runfile : Path
            Path to the master pyCIAO .run file.

        Returns
        -------
        list[RunRecord]
            Numbered run records in their original order.

        Raises
        ------
        OSError
            If the run file cannot be read.
        ValueError
            If the header, parameter columns, run numbers or
            tab-separated rows are malformed.
        """
        try:
            lines = runfile.read_text(encoding="utf-8").splitlines()
        except OSError as e:
            raise OSError(f"Could not read run file {runfile}: {e}") from e

        header_index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.lstrip().startswith("#run")
            ),
            None,
        )

        if header_index is None:
            raise ValueError(f'Invalid run file {runfile}: missing "#run" header')

        header_fields = self._split_tabfields(lines[header_index])
        if not header_fields:
            raise ValueError(f"Invalid empty table header in {runfile}")

        first_header = header_fields[0].lstrip("#").strip().casefold()
        if first_header != "run":
            raise ValueError(
                f'Invalid first table column in {runfile}: expected "#run", '
                f"got {header_fields[0]!r}"
            )

        parameter_headers = header_fields[1:]
        if len(parameter_headers) != len(set(parameter_headers)):
            raise ValueError(f"Duplicate parameter headers found in {runfile}")

        selected_headers: dict[str, str] = {}
        for column in self.loop_columns:
            command_key = column.command.strip().casefold()
            matches = [
                header
                for header in parameter_headers
                if self._command_word(header) == command_key
            ]

            if not matches:
                available = ", ".join(parameter_headers) or "<none>"
                raise ValueError(
                    f"Run file {runfile} has no loop command "
                    f'"{column.command}". Available loop columns: {available}'
                )

            if len(matches) > 1:
                headers = ", ".join(matches)
                raise ValueError(
                    f"Run file {runfile} has multiple columns matching "
                    f'"{column.command}": {headers}'
                )

            selected_headers[command_key] = matches[0]

        records: list[RunRecord] = []
        seen_run_ids: set[int] = set()

        for line_number, line in enumerate(
            lines[header_index + 1 :],
            start=header_index + 2,
        ):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            fields = self._split_tabfields(line)
            expected_fields = len(header_fields)

            if len(fields) != expected_fields:
                raise ValueError(
                    f"Malformed row {line_number} in {runfile}: expected "
                    f"{expected_fields} tab-separated fields from the header, "
                    f"but found {len(fields)}."
                )

            try:
                run_id = int(fields[0])
            except ValueError as e:
                raise ValueError(
                    f"Invalid run number {fields[0]!r} on line {line_number} "
                    f"of {runfile}"
                ) from e

            if run_id < 1:
                raise ValueError(
                    f"Run number must be positive on line {line_number} of {runfile}"
                )

            if run_id in seen_run_ids:
                raise ValueError(f"Duplicate run number {run_id} in {runfile}")

            all_parameters = dict(zip(parameter_headers, fields[1:], strict=True))

            parameters = {
                exact_header: all_parameters[exact_header]
                for exact_header in selected_headers.values()
            }

            records.append(RunRecord(run_id=run_id, parameters=parameters))
            seen_run_ids.add(run_id)

        if not records:
            raise ValueError(f"No run rows found in {runfile}")

        return records

    def _get_loop_value(self, record: RunRecord, column: LoopColumn) -> float:
        """
        Extract and convert a selected loop-parameter value.

        Parameters
        ----------
        record : RunRecord
            Numbered run containing the original parameter values.
        column : LoopColumn
            Parameter definition specifying the command name,
            input scale and multiplicative conversion factor.

        Returns
        -------
        float
            Converted numerical parameter value.

        Raises
        ------
        ValueError
            If the requested parameter is missing, ambiguous,
            non-numeric or non-finite.
        """
        command_key = column.command.strip().casefold()
        matches = [
            (header, value)
            for header, value in record.parameters.items()
            if self._command_word(header) == command_key
        ]

        if not matches:
            available = ", ".join(record.parameters) or "<none>"
            raise ValueError(
                f'Run {record.run_id} has no loop command "{column.command}". '
                f"Available loop columns: {available}"
            )

        if len(matches) > 1:
            headers = ", ".join(header for header, _ in matches)
            raise ValueError(
                f"Run {record.run_id} has multiple loop columns matching "
                f'"{column.command}": {headers}'
            )

        header, text_value = matches[0]

        try:
            value = float(text_value)
        except ValueError as e:
            raise ValueError(
                f"Run {record.run_id}: value {text_value!r} for loop "
                f"column {header!r} is not numeric"
            ) from e

        if not np.isfinite(value):
            raise ValueError(
                f"Run {record.run_id}: input value for {header!r} is not finite"
            )

        if column.input_scale == "log10":
            with np.errstate(over="ignore", invalid="ignore"):
                value = 10.0**value

        value *= column.factor

        if not np.isfinite(value):
            raise ValueError(
                f"Run {record.run_id}: converted value for {header!r} is not finite"
            )

        return float(value)

    @staticmethod
    def _load_map(map_path: Path) -> NDArray[np.float64]:
        """
        Load and validate one heating/cooling map.

        The input file must contain at least four columns:
        temperature, heating coefficient, cooling coefficient
        and mean molecular weight.

        The method checks for missing or malformed data,
        non-finite values, non-positive temperatures and mean
        molecular weights, and negative heating or cooling values.

        Temperature rows are sorted into increasing order when
        necessary. Duplicate temperatures are rejected.

        Parameters
        ----------
        map_path : Path
            Path to the heating/cooling map.

        Returns
        -------
        numpy.ndarray
            Validated two-dimensional array containing the
            first four physical columns, sorted by temperature.

        Raises
        ------
        FileNotFoundError
            If the input map does not exist.
        ValueError
            If the file is empty, malformed or contains
            invalid numerical values.
        """
        if not map_path.is_file():
            raise FileNotFoundError(f"Missing data map: {map_path}")

        if map_path.stat().st_size == 0:
            raise ValueError(f"Data map is empty: {map_path}")

        try:
            raw_data = np.loadtxt(
                map_path,
                comments="#",
                dtype=np.float64,
                ndmin=2,
            )
        except (OSError, ValueError) as e:
            raise ValueError(f"Could not load data map {map_path}: {e}") from e

        if raw_data.ndim != 2 or raw_data.shape[0] == 0 or raw_data.shape[1] < 4:
            raise ValueError(
                f"Data file {map_path} must have at least 4 columns "
                f"(temperature, heating, cooling, MMW); got shape "
                f"{raw_data.shape}"
            )

        data = np.asarray(raw_data[:, :4], dtype=np.float64)
        finite_rows = np.all(np.isfinite(data), axis=1)
        if not np.all(finite_rows):
            bad_rows = np.flatnonzero(~finite_rows)
            raise ValueError(
                f"Non-finite values detected in {map_path} at zero-based "
                f"rows {bad_rows.tolist()}"
            )

        temperatures = data[:, 0]
        heating = data[:, 1]
        cooling = data[:, 2]
        mmw = data[:, 3]

        if np.any(temperatures <= 0.0):
            raise ValueError(f"Non-positive temperatures detected in {map_path}")

        if np.any(mmw <= 0.0):
            raise ValueError(f"Non-positive MMW detected in {map_path}")

        if np.any(heating < 0.0):
            raise ValueError(f"Negative heating values found in {map_path}")

        if np.any(cooling < 0.0):
            raise ValueError(f"Negative cooling values found in {map_path}")

        sort_index = np.argsort(temperatures, kind="stable")
        if not np.array_equal(sort_index, np.arange(len(temperatures))):
            logger.warning(f"Sorting non-monotonic temperatures in {map_path}")
            data = data[sort_index]
            temperatures = data[:, 0]

        if np.any(np.diff(temperatures) == 0.0):
            raise ValueError(f"Duplicate temperatures detected in {map_path}")

        return data

    def _process_map(self, map_path: Path, record: RunRecord) -> NDArray[np.float64]:
        """
        Combine one heating/cooling map with its loop parameters.

        The selected loop-parameter values are repeated for every
        temperature row and prepended to the physical data columns.

        Parameters
        ----------
        map_path : Path
            Path to the heating/cooling map.
        record : RunRecord
            Corresponding entry in the master .run file.

        Returns
        -------
        numpy.ndarray
            Selected loop-parameter columns followed by temperature,
            heating, cooling and mean molecular weight.
        """
        map_data = self._load_map(map_path)
        n_rows = map_data.shape[0]

        parameter_columns = [
            np.full(
                n_rows,
                self._get_loop_value(record, column),
                dtype=np.float64,
            )
            for column in self.loop_columns
        ]

        if parameter_columns:
            return np.column_stack((*parameter_columns, map_data))

        return map_data

    def write_table(self, outdir: str | Path = ".", outfile: str | None = None) -> Path:
        """
        Write the combined heating/cooling table.

        The individual Cloudy maps are processed in the order
        recorded in the master .run file.

        All maps must contain identical temperature grids.

        The resulting table is first written to a temporary file.
        The destination file is replaced only after every map
        has been processed successfully.

        Parameters
        ----------
        outdir : str or Path, optional
            Directory where the combined table will be saved.
            Defaults to the current working directory.
        outfile : str or None, optional
            Output filename. If None, defaults to
            '{run_name}_cooltable.dat'.

        Returns
        -------
        Path
            Path to the generated heating/cooling table.

        Raises
        ------
        FileNotFoundError
            If the master .run file or a required data map is missing.
        ValueError
            If a data map is malformed or the temperature grids
            differ between runs.
        """
        runfile = self.run_dir / f"{self.run_name}.run"
        if not runfile.is_file():
            raise FileNotFoundError(f"Master run file not found: {runfile}")

        records = self._read_run_file(runfile)

        outdir = Path(outdir).expanduser()
        outdir.mkdir(parents=True, exist_ok=True)

        filename = outfile or f"{self.run_name}_cooltable.dat"
        outpath = outdir / filename

        tmp_path = outpath.with_name(f".{outpath.name}.tmp")

        headers = [
            *(column.output_header for column in self.loop_columns),
            "TEMPERATURE[K]",
            "HEATING[erg_cm^3_s^-1]",
            "COOLING[erg_cm^3_s^-1]",
            "MMW[amu]",
        ]
        header = "  ".join(headers)
        formats = ["%.7E"] * len(headers)

        logger.info(f"Generating heating/cooling table from {runfile} to {outpath}...")

        try:
            with tmp_path.open("w", encoding="utf-8") as output:
                output.write(f"{header}\n")

                reference_temperatures = None

                for record in records:
                    map_path = self.run_dir / f"{self.run_name}_run{record.run_id}.dat"
                    data = self._process_map(map_path, record)

                    temperature_col = len(self.loop_columns)
                    temperatures = data[:, temperature_col]

                    if reference_temperatures is None:
                        reference_temperatures = temperatures.copy()
                    elif not np.array_equal(temperatures, reference_temperatures):
                        raise ValueError(f"Inconsistent temperature grid in {map_path}.")

                    np.savetxt(output, data, fmt=formats, delimiter="  ")

            tmp_path.replace(outpath)

        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        logger.info("Wrote %d run maps to %s", len(records), outpath)
        return outpath
