#!/usr/bin/env python3

from __future__ import annotations

import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class LoopColumn:
    """
    Describe one loop parameter from the pyCIAO `.run` file.
    """
    command: str
    output_header: str
    input_scale: Literal["linear", "log10"] = "linear"
    factor: float = 1.0

@dataclass(frozen=True)
class RunRecord:
    """
    One data row parsed from the pyCIAO `.run` file.
    """
    run_id: int
    parameters: dict[str, str]

class HeatingCoolingTables:
    """
    Process and format heating and cooling tables for HD/MHD codes.

    This class reads the outputs of pyCIAO to generate a single table
    containing temperature, mean molecular weight, heating, and cooling.

    Attributes
    ----------
    run_dir : Path
        Directory containing the pyCIAO run file and data maps.
    run_name : str
        The common identifier (stem) of the pyCIAO run.
    """

    DEFAULT_LOOP_COLUMNS: tuple[LoopColumn, ...] = (
        LoopColumn(
            command='hden',
            output_header='HDEN[cm^-3]',
            input_scale='log10',
        ),
    )

    def __init__(self, run_dir: str | Path, run_name: str, loop_columns: Sequence[LoopColumn] | None = None) -> None:
        """
        Initialise the processor with the location and ID of the run.

        Parameters
        ----------
        run_dir : str or Path
            The folder containing the pyCIAO run files.
        run_name : str
            The unique identifier for the run.
            The code expects to find '{run_name}.run' and associated
            '{run_name}_runX.dat' files in the run_dir.
        loop_columns
            Loop parameters to copy into the final table.
            By default, the logarithmic `hden` value is converted to linear
            number density.
        """
        self.run_dir  = Path(run_dir).expanduser()
        self.run_name = run_name.removesuffix('.run')
        self.loop_columns = (
            self.DEFAULT_LOOP_COLUMNS
            if loop_columns is None
            else tuple(loop_columns)
        )

        if not self.run_name:
            raise ValueError('run_name must not be empty')
        
        commands = [column.command.strip().casefold() for column in self.loop_columns]
        if len(commands) != len(set(commands)):
            raise ValueError('loop_columns contains duplicate command names')

        for column in self.loop_columns:
            if not column.command.strip():
                raise ValueError("LoopColumn.command must not be empty")
            if column.input_scale not in {'linear', 'log10'}:
                raise ValueError(
                    f'Unsupported input scale {column.input_scale!r} for '
                    f'{column.command!r}'
                )
            if not np.isfinite(column.factor):
                raise ValueError(
                    f'LoopColumn.factor must be finite for {column.command!r}'
                )

    @staticmethod
    def _split_tabfields(line: str) -> list[str]:
        """
        Split a tabular .run file preserving spaces in commands.
        """
        return [field.strip() for field in line.rstrip('\n').split('\t')]

    @staticmethod
    def _command_word(command_header: str) -> str:
        """
        Return the first word of a loop-command header.
        """
        parts = command_header.strip().split(maxsplit=1)
        return parts[0].casefold() if parts else ''

    def _read_run_file(self, runfile: Path) -> list[RunRecord]:
        """
        Parse the tabular section of a pyCIAO run file.
        """
        try:
            lines = runfile.read_text(encoding='utf-8').splitlines()
        except OSError as e:
            raise OSError(f'Could not read run file {runfile}: {e}') from e

        header_index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.lstrip().startswith('#run')
            ),
            None,
        )

        if header_index is None:
            raise ValueError(f'Invalid run file {runfile}: missing "#run" header')

        header_fields = self._split_tabfields(lines[header_index])
        if not header_fields:
            raise ValueError(f'Invalid empty table header in {runfile}')

        first_header = header_fields[0].lstrip('#').strip().casefold()
        if first_header != 'run':
            raise ValueError(
                f'Invalid first table column in {runfile}: expected "#run", '
                f'got {header_fields[0]!r}'
            )

        parameter_headers = header_fields[1:]
        if len(parameter_headers) != len(set(parameter_headers)):
            raise ValueError(f'Duplicate parameter headers found in {runfile}')

        selected_headers: dict[str,str] = {}
        for column in self.loop_columns:
            command_key = column.command.strip().casefold()
            matches = [
                header
                for header in parameter_headers
                if self._command_word(header) == command_key
            ]

            if not matches:
                available = ', '.join(parameter_headers) or "<none>"
                raise ValueError(
                    f'Run file {runfile} has no loop command '
                    f'"{column.command}". Available loop columns: {available}'
                )

            if len(matches) > 1:
                headers = ", ".join(matches)
                raise ValueError(
                    f'Run file {runfile} has multiple columns matching '
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
            if not stripped or stripped.startswith('#'):
                continue

            fields = self._split_tabfields(line)
            expected_fields = len(header_fields)

            if len(fields) != expected_fields:
                raise ValueError(
                    f'Malformed row {line_number} in {runfile}: expected '
                    f'{expected_fields} tab-separated fields from the header, '
                    f'but found {len(fields)}.'
                )

            try:
                run_id = int(fields[0])
            except ValueError as e:
                raise ValueError(
                    f'Invalid run number {fields[0]!r} on line {line_number} '
                    f'of {runfile}'
                ) from e

            if run_id < 1:
                raise ValueError(f'Run number must be positive on line {line_number} of {runfile}')

            if run_id in seen_run_ids:
                raise ValueError(f'Duplicate run number {run_id} in {runfile}')
            
            all_parameters = dict(
                zip(parameter_headers, fields[1:], strict=True)
            )

            parameters = {
                exact_header: all_parameters[exact_header]
                for exact_header in selected_headers.values()
            }

            records.append(RunRecord(run_id=run_id, parameters=parameters))
            seen_run_ids.add(run_id)

        if not records:
            raise ValueError(f'No run rows found in {runfile}')

        return records

    def _get_loop_value(self, record: RunRecord, column: LoopColumn) -> float:
        """
        Extract and convert one requested loop value.
        """
        command_key = column.command.strip().casefold()
        matches = [
            (header, value)
            for header, value in record.parameters.items()
            if self._command_word(header) == command_key
        ]

        if not matches:
            available = ', '.join(record.parameters) or '<none>'
            raise ValueError(
                f'Run {record.run_id} has no loop command "{column.command}". '
                f'Available loop columns: {available}'
            )

        if len(matches) > 1:
            headers = ', '.join(header for header, _ in matches)
            raise ValueError(
                f'Run {record.run_id} has multiple loop columns matching '
                f'"{column.command}": {headers}'
            )

        header, text_value = matches[0]

        try:
            value = float(text_value)
        except ValueError as e:
            raise ValueError(
                f'Run {record.run_id}: value {text_value!r} for loop '
                f'column {header!r} is not numeric'
            ) from e

        if not np.isfinite(value):
            raise ValueError(f'Run {record.run_id}: input value for {header!r} is not finite')

        if column.input_scale == 'log10':
            with np.errstate(over='ignore', invalid='ignore'):
                value = 10.0**value

        value *= column.factor

        if not np.isfinite(value):
            raise ValueError(
                f'Run {record.run_id}: converted value for {header!r} '
                f'is not finite'
            )

        return float(value)

    @staticmethod
    def _load_map(map_path: Path) -> NDArray[np.float64]:
        """
        Load and validate one heating/cooling map.
        """
        if not map_path.is_file():
            raise FileNotFoundError(f'Missing data map: {map_path}')

        if map_path.stat().st_size == 0:
            raise ValueError(f'Data map is empty: {map_path}')

        try:
            raw_data = np.loadtxt(
                map_path,
                comments='#',
                dtype=np.float64,
                ndmin=2,
            )
        except (OSError, ValueError) as e:
            raise ValueError(f'Could not load data map {map_path}: {e}') from e

        if (
            raw_data.ndim != 2
            or raw_data.shape[0] == 0
            or raw_data.shape[1] < 4
        ):
            raise ValueError(
                f'Data file {map_path} must have at least 4 columns '
                f'(temperature, heating, cooling, MMW); got shape '
                f'{raw_data.shape}'
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
            raise ValueError(f'Non-positive temperatures detected in {map_path}')

        if np.any(mmw <= 0.0):
            raise ValueError(f'Non-positive MMW detected in {map_path}')

        if np.any(heating < 0.0):
            raise ValueError(f'Negative heating values found in {map_path}')

        if np.any(cooling < 0.0):
            raise ValueError(f'Negative cooling values found in {map_path}')

        sort_index = np.argsort(temperatures, kind='stable')
        if not np.array_equal(sort_index, np.arange(len(temperatures))):
            logger.warning(f'Sorting non-monotonic temperatures in {map_path}')
            data = data[sort_index]
            temperatures = data[:, 0]

        if np.any(np.diff(temperatures) == 0.0):
            raise ValueError(f'Duplicate temperatures detected in {map_path}')

        return data

    def _process_map(self, map_path: Path, record: RunRecord) -> NDArray[np.float64]:
        """
        Combine one map with its loop-parameter values.
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

    def write_table(self, outdir: str | Path = '.', outfile: str | None = None) -> Path:
        """
        Write the heating/cooling rates table.

        Parameters
        ----------
        outdir : str or Path, optional
            Directory where the table will be saved.
            Defaults to '.' (current directory).
        outfile : str, optional
            Name of the output file.
            If None, defaults to '{run_name}_cooltable.dat'.
            This file is saved in the current directory.

        Returns
        -------
        Path 
            The full path to the generated table.
        """
        runfile = self.run_dir / f'{self.run_name}.run'
        if not runfile.is_file():
            raise FileNotFoundError(f'Master run file not found: {runfile}')

        records = self._read_run_file(runfile)

        outdir = Path(outdir).expanduser()
        outdir.mkdir(parents=True, exist_ok=True)

        filename = outfile or f'{self.run_name}_cooltable.dat'
        outpath = outdir / filename

        tmp_path = outpath.with_name(f'.{outpath.name}.tmp')

        headers = [
            *(column.output_header for column in self.loop_columns),
            "TEMPERATURE[K]",
            "HEATING[erg_cm^3_s^-1]",
            "COOLING[erg_cm^3_s^-1]",
            "MMW[amu]",
        ]
        header = "  ".join(headers)
        formats = ["%.7E"] * len(headers)

        logger.info(f'Generating heating/cooling table from {runfile} to {outpath}...')

        try:
            with tmp_path.open("w", encoding="utf-8") as output:
                output.write(f"{header}\n")

                for record in records:
                    map_path = (
                        self.run_dir
                        / f"{self.run_name}_run{record.run_id}.dat"
                    )
                    data = self._process_map(map_path, record)
                    np.savetxt(
                        output,
                        data,
                        fmt=formats,
                        delimiter="  ",
                    )

            tmp_path.replace(outpath)

        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        logger.info("Wrote %d run maps to %s", len(records), outpath)
        return outpath
