#!/usr/bin/env python3

import logging
from pathlib import Path

import h5py
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

"""
Generate ionisation tables from Cloudy outputs.
"""

class IonTables:
    """
    Generate ionisation-fraction tables from pyCIAO/Cloudy outputs.

    This class reads the established pyCIAO .run file and the
    ionisation-fraction maps generated for individual Cloudy runs.

    The results are assembled into a multidimensional HDF5 table
    compatible with Trident.

    The final dataset dimensions are ordered as:

        (ionisation stage, density, redshift, temperature)

    For calculations performed only at z=0, the ionisation grid
    is duplicated along the redshift axis, producing coordinates
    z=0 and z=1e-4.

    The second redshift slice is introduced for Trident
    interpolation compatibility. It does not represent an
    independent Cloudy calculation or redshift evolution.

    Parameters
    ----------
    run_dir : str or Path
        Directory containing the pyCIAO .run file and
        individual ionisation-fraction maps.
    run_name : str
        Common identifier for the simulation run.
        The '.run' suffix may be supplied optionally.
    elements : str
        Space-separated chemical element symbols to include
        in the final HDF5 table, for example 'H C N O'.

    Attributes
    ----------
    run_dir : Path
        Directory containing the input files.
    run_name : str
        Identifier for the simulation run.
    runfile : Path
        Path to the master .run file.
    outfile : Path
        Path to the generated ionisation HDF5 table.
    """

    def __init__(self, run_dir: str | Path, run_name: str, elements: str) -> None:
        """
        Locate the run files and select the requested chemical elements.
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
        Parse the master pyCIAO run file.

        The method extracts the ordered loop parameters and their
        sampled values, together with the total number of runs.

        The ordering is preserved because it determines how the
        individual ionisation maps are assembled into the
        multidimensional grid.

        Returns
        -------
        parameter_values : list[list[float]]
            Numerical values associated with each loop parameter.
        parameter_names : list[str]
            Corresponding loop-command names.
        n_runs : int
            Number of runs recorded in the master run file.

        Raises
        ------
        ValueError
            If the number of runs is inconsistent with the
            multidimensional parameter grid.
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
        Read one ionisation-fraction map.

        Parameters
        ----------
        map_path : str or Path
            Path to a file named
            '{run_name}_runX_ELEMENT.dat'.

        Returns
        -------
        temperature : numpy.ndarray
            Logarithmic temperatures, log10(T/K).
        ion_fraction : numpy.ndarray
            Logarithmic ionisation fractions for the different
            ionisation stages of the selected element.

        Raises
        ------
        RuntimeError
            If the input map cannot be read.
        ValueError
            If the map does not contain the expected data columns.
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
        Assemble and store the ionisation table for one element.

        Individual ionisation maps are combined according to the
        parameter ordering recorded in the master .run file.

        The ionisation-stage dimension is moved to the first axis
        to produce the ordering required by Trident.

        For a single-redshift calculation at z=0, the ionisation
        grid is duplicated at z=1e-4.

        The resulting HDF5 dataset contains the attributes:

            Temperature : logarithmic temperature grid
            Parameter1  : hydrogen number-density grid
            Parameter2  : redshift grid

        Parameters
        ----------
        element : str
            Chemical element symbol.

        Raises
        ------
        FileNotFoundError
            If a required ionisation map is missing.
        ValueError
            If temperature grids, ion-fraction dimensions or
            redshift configuration are inconsistent.
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
        Generate the HDF5 ionisation tables for the selected elements.

        Each element is stored as a separate HDF5 dataset containing
        the logarithmic ionisation fractions.

        The output file follows the naming convention:

            {run_name}_iontable.h5

        The file is opened in append mode. Existing datasets with
        the same element names are not overwritten automatically.

        Raises
        ------
        ValueError
            If no chemical elements were specified or the input
            parameter grids are inconsistent.
        FileNotFoundError
            If a required ionisation map is missing.
        """
        if not self.elements:
            logger.warning("No elements specified!")
            raise ValueError("Cannot write table: No elements specified.")

        for element in self.elements:
            self._process_element(element)
