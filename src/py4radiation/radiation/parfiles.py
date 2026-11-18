#!/usr/bin/env python3

"""
Generate pyCIAO parameter files for Cloudy calculations.

Supports heating/cooling and ion fraction calculations over user-defined
density and temperature grids.
"""

from pathlib import Path
from typing import Literal

import numpy as np


class ParameterFiles:
    """
    Generate parameter files for pyCIAO/Cloudy calculations.

    This class prepares configuration files for calculating
    radiative heating and cooling maps (mode 1) and ionisation
    fraction maps (mode 3) using Cloudy. The mode numbers keep
    compatibility with CIAOLoop (B. Smith).

    The generated files define the physical parameter grids
    and reference a previously generated radiation-field
    input file.

    Parameters
    ----------
    cloudy_path : str or Path
        Path to the Cloudy executable.
    run_name : str
        Identifier used to name parameter files and Cloudy outputs.
    elements : str
        Space-separated chemical element symbols for ionisation
        calculations, for example 'H C N O'. Supports until Zn.
    normalisation: {1, 2}
        Normalisation factor for heating/cooling rates.
        (1) for n_H^2 and (2) for n_e * n_H.
        Default is 1.
    redshift : str, optional
        Redshift (currently only the near Universe z=0 is supported).
        Default is 0.0000e+00.
    n_limits : tuple, optional
        Limits of the hydrogen number density range in logspace (cm^-3).
        Default is (-9, 4).
    T_limits : tuple
        Limits of the temperature range in logspace (K).
        Default is (1, 9).
    n_spacing: float
        Density-grid spacing in dex. Takes precedence over n_points.
        Default is 0.125.
    n_points : int
        Alternative number of density samles.
        Used when n_spacing is None.
    T_points : int
        Number of points for temperature in logspace.
        Default is 321.
    """

    def __init__(
        self,
        cloudy_path: str | Path,
        run_name: str,
        elements: str,
        normalisation: Literal[1, 2] = 1,
        redshift: str = "0.0000e+00",
        n_limits: tuple = (-9, 4),
        T_limits: tuple = (1, 9),
        n_spacing: float = 0.125,
        n_points: int | None = None,
        T_points: int = 321,
    ) -> None:
        """
        Initialise the parameter-file generator and density-grid settings.
        """
        self.cloudy_path = str(cloudy_path)
        self.run_name = run_name
        self.elements = elements
        self.normalisation = normalisation
        self.redshift = redshift

        self.root_dir = Path.cwd()

        self.n_lo, self.n_hi = n_limits
        self.T_lo, self.T_hi = T_limits

        if n_spacing is not None and n_points is not None:
            print("Both n_spacing and n_points were provided. Using n_spacing...")

        if n_spacing is not None:
            if not np.isfinite(n_spacing) or n_spacing <= 0:
                raise ValueError("n_spacing must be positive and finite.")

            self.n_spacing = n_spacing

        elif n_points is not None:
            if n_points < 2:
                raise ValueError("n_points must be at least 2.")

            self.n_spacing = (self.n_hi - self.n_lo) / (n_points - 1)

        else:
            raise ValueError("Either n_spacing or n_points must be provided.")

        self.T_points = T_points

    def _get_header(self, output_subdir: str, run_mode: Literal[1, 3]) -> list[str]:
        """
        Generate the configuration header shared by both calculation modes.

        Parameters
        ----------
        output_subdir : str
            Output directory for selected mode.
        run_mode : {1, 3}
            Run (1) Heating & Cooling map or (3) Ion Fraction map.

        Returns
        -------
        list[str]
            Configuration header lines for the parameter file.
        """
        outdir_path = self.root_dir / output_subdir

        return [
            "#####################################################",
            "################## RUN  PARAMETERS ##################",
            "",
            "# path to CLOUDY executable",
            f"cloudyExe              = {self.cloudy_path}",
            "",
            "# save raw output from CLOUDY",
            "saveCloudyOutputFiles   = 0",
            "",
            "# exit if CLOUDY crashes",
            "exitOnCrash             = 1",
            "",
            "# run name",
            f"outputFilePrefix       = {self.run_name}",
            "",
            "# output path",
            f"outputDir              = {outdir_path}",
            "",
            "# index of first run",
            "runStartIndex           = 1",
            "",
            "# TEST",
            "test                    = 0",
            "",
            "# run mode",
            f"cloudyRunMode          = {run_mode}",
            "",
        ]

    def _get_loops(self) -> list[str]:
        """
        Generate the density and radiation-field loop definitions.

        The density loop specifies the hydrogen number-density grid.
        The radiation-field loop references the Cloudy input file
        corresponding to the selected redshift.

        Returns
        -------
        list[str]
            Commands defining the density and radiation-field loops.
        """
        sed_pattern = self.root_dir / f"{self.run_name}_z*.out"

        init_cmd = f'loop [init "{sed_pattern}"] {self.redshift}'

        return [
            "#####################################################",
            "####################### LOOPS #######################",
            "",
            "command stop zone 1",
            "",
            "command set dr 0",
            "",
            "command iterate to convergence",
            "",
            f"loop [hden] ({self.n_lo};{self.n_hi};{self.n_spacing})",
            "",
            init_cmd,
        ]

    def hc_parfile(self) -> Path:
        """
        Generate the heating/cooling parameter file.

        The generated configuration uses Cloudy run mode 1 and
        normalises the heating and cooling rates by the selected
        factor (coolingScaleFactor).

        Returns
        -------
        Path
            Path to the generated '{run_name}_hc.par' file.
        """
        filename = f"{self.run_name}_hc.par"
        file_path = self.root_dir / filename

        lines = self._get_header(output_subdir="hc", run_mode=1)

        lines.extend(
            [
                "#####################################################",
                "########## HEATING & COOLING MAP PARAMETERS #########",
                "",
                "# min T",
                f"coolingMapTmin = 1e{self.T_lo}",
                "",
                "# max T",
                f"coolingMapTmax = 1e{self.T_hi}",
                "",
                "# T resolution (log points)",
                f"coolingMapTpoints = {self.T_points}",
                "",
                "# scale factor (1 - n_H^2, 2 - n_H * n_e)",
                f"coolingScaleFactor = {self.normalisation}",
                "",
            ]
        )

        lines.extend(self._get_loops())

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
            f.write("\n")

        return file_path

    def ib_parfile(self) -> Path:
        """
        Generate the ion-fraction parameter file.

        THe generated configuration uses Cloudy run mode 3
        and includes the requested chemical elements and
        temperature grids.

        Returns
        -------
        Path
            Path to the generated '{run_name}_ib.par' file.
        """
        filename = f"{self.run_name}_ib.par"
        file_path = self.root_dir / filename

        lines = self._get_header(output_subdir="ib", run_mode=3)

        lines.extend(
            [
                "#####################################################",
                "############ ION FRACTION MAP PARAMETERS ############",
                "",
                "# min T",
                f"coolingMapTmin = 1e{self.T_lo}",
                "",
                "# max T",
                f"coolingMapTmax = 1e{self.T_hi}",
                "",
                "# T resolution (log points)",
                f"coolingMapTpoints = {self.T_points}",
                "",
                "# elements",
                f"ionFractionElements = {self.elements}",
                "",
            ]
        )

        lines.extend(self._get_loops())

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
            f.write("\n")

        return file_path
