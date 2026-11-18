#!/usr/bin/env python3

from pathlib import Path
from typing import Literal

import numpy as np


class ParameterFiles:
    """
    Generate CIAOLoop parameter files for pyCIAO.

    This class prepares configuration files for calculating
    radiative heating and cooling maps (hc) and ionisation
    fraction maps (ib) using Cloudy.
    """

    def __init__(
        self,
        cloudy_path: str | Path,
        run_name: str,
        elements: str,
        redshift: str = "0.0000e+00",
        n_limits: tuple = (-9, 4),
        T_limits: tuple = (1, 9),
        n_spacing: float = 0.125,
        n_points: int | None = None,
        T_points: int = 321,
    ) -> None:
        """
        Initialise the parameter generator.

        Parameters
        ----------
        cloudy_path : str | Path
            Path to the Cloudy executable.
        run_name : str
            Name for the current CIAOLoop run.
        elements : str
            String of elements for ion fraction calculation (e.g., 'H C N O').
        redshift : str
            Redshift (currently only the near Universe z=0 is supported).
            Default is 0.0000e+00.
        n_limits : tuple
            Limits of the hydrogen number density range in logspace (cm^-3).
            Default is (-9, 4).
        T_limits : tuple
            Limits of the temperature range in logspace (K).
            Default is (1, 9).
        n_spacing: float
            Spacing for hydrogen number density in logspace.
            Default is 0.05.
        n_points : int
            Number of points for hydrogen number density in logspace.
            Default is None.
        T_points : int
            Number of points for temperature in logspace.
            Default is 321.
        """
        self.cloudy_path = str(cloudy_path)
        self.run_name = run_name
        self.elements = elements
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
        Generate the header lines shared by both parameter files.

        Parameters
        ----------
        output_subdir : str
            Output directory for selected mode.
        run_mode : {1, 3}
            Run (1) Heating & Cooling map or (3) Ion Fraction map.

        Returns
        -------
        list[str]
            Header of parameter file.
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
        Generate the loop commands section.

        Parameters
        ----------
        is_ib : bool
            Add a parameter for Ion Fraction maps.
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
        Generate and write the CIAOLoop parameter file for heating & cooling.
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
                "coolingScaleFactor = 1",
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
        Generate and write the CIAOLoop parameter file for ion fractions.
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
