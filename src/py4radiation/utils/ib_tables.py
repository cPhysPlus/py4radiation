#!/usr/bin/env python3

import logging
from pathlib import Path

import h5py
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class IonTables:
    """
    A class to generate ion fraction tables from pyCIAO/Cloudy output files.

    This class parses a simulation run configuration, loads distributed
    ion fraction maps, and generates a single HDF5 file suitable for
    astrophysical codes.

    Attributes
    ----------
    run_dir : Path
        Directory containing the pyCIAO run file and data maps.
    run_name : str
        The common identifier of the pyCIAO run.
    """

    def __init__(self, run_dir: str | Path, run_name: str, elements: str) -> None:
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
        elements : Iterable[str]
            List of elements for the ion fraction tables.
        """
        self.run_dir = Path(run_dir)
        self.run_name = run_name.removesuffix(".run")
        self.elements = elements.split()

        self.runfile = Path(run_dir) / f"{self.run_name}.run"
        self.outfile = Path(run_dir) / f"{self.run_name}_iontable.h5"

        if not self.runfile.exists():
            raise FileNotFoundError(f"Master run file not found: {self.runfile}")

    def _parse_runfile(self) -> tuple[list[list[float]], list[str], int]:
        """
        Parse the run file for loop parameters and run count.
        """
        with open(self.runfile, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f]

        parameter_values: list[list[float]] = []
        parameter_names: list[str] = []
        collecting = False
        n_runs = 0

        for i, line in enumerate(lines):
            if collecting:
                if line == "#":
                    collecting = False
                else:
                    key, vals = line.split(":", 1)
                    parameter_names.append(key[2:])
                    parameter_values.append([float(v) for v in vals.split()])
            elif line.startswith("# Loop commands and values"):
                collecting = True
            elif line.startswith("#run"):
                n_runs = len(lines) - i - 1
                break

        grid_shape = [len(v) for v in parameter_values]
        if grid_shape and n_runs != int(np.prod(grid_shape)):
            raise ValueError("Run count does not match parameter grid size.")

        return parameter_values, parameter_names, n_runs

    def _read_map(
        self, map_path: str | Path
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """
        Read a single '*_runX_ELEMENT.dat' file.
        """
        try:
            data = np.loadtxt(map_path, comments="#", ndmin=2)
        except Exception as e:
            raise RuntimeError(f"Failed to read map file {map_path}: {e}.") from e

        if data.shape[1] < 2:
            raise ValueError(f"Invalid map format in {map_path}.")

        temperature = data[:, 0].astype(np.float64)
        ion_fraction = data[:, 1:].astype(np.float64)

        return temperature, ion_fraction

    def _process_element(self, element: str) -> None:
        """
        Process each element provided in the run.
        """
        logger.info(f"Processing element {element}...")

        parameter_values, parameter_names, n_runs = self._parse_runfile()
        grid_shape = [len(v) for v in parameter_values]

        temperature: NDArray[np.float64] | None = None
        ion_grid: NDArray[np.float64] | None = None

        for run_idx in range(n_runs):
            map_path = self.run_dir / f"{self.run_name}_run{run_idx + 1}_{element}.dat"
            if not map_path.exists():
                raise FileNotFoundError(f"Missing map file: {map_path}.")

            temp, ion_frac = self._read_map(map_path)

            if ion_grid is None:
                temperature = temp
                shape = tuple(grid_shape) + ion_frac.shape
                ion_grid = np.zeros(shape, dtype=np.float64)

            else:
                if not np.array_equal(temp, temperature):
                    raise ValueError(f"Inconsistent temperature grid in {map_path}.")

                if ion_frac.shape != ion_grid.shape[-2:]:
                    raise ValueError(f"Inconsistent ion fraction dimension in {map_path}")

            idx = np.unravel_index(run_idx, grid_shape) if grid_shape else (run_idx,)
            ion_grid[idx] = ion_frac

        assert temperature is not None and ion_grid is not None

        ion_grid = np.rollaxis(ion_grid, -1)

        if (len(parameter_values) != 2 or not parameter_names[1].startswith("init ")):
            raise ValueError("Expected density and radiation-field loops for the Trident ionisation table.")

        redshifts = parameter_values[1]

        if len(redshifts) == 1:
            if redshifts[0] != 0.0:
                raise ValueError("Redshift duplication currently supports only z=0.")

            ion_grid = np.repeat(ion_grid, repeats=2, axis=2)

            parameter_values[1] = [0.0, 1.0e-4]

            logger.info("Dubplicated the z=0 ionisation grid at z=1e-4 for Trident compatibility.")

        with h5py.File(self.outfile, "a") as f_out:
            ds = f_out.create_dataset(element, data=ion_grid)

            ds.attrs["Temperature"] = temperature

            for i, values in enumerate(parameter_values, start=1):
                ds.attrs[f"Parameter{i}"] = np.asarray(values, dtype=np.float64)

    def write_table(self) -> None:
        """
        Write the ion fractions table.
        """
        if not self.elements:
            logger.warning("No elements specified!")
            raise ValueError("Cannot write table: No elements specified.")

        for element in self.elements:
            self._process_element(element)
