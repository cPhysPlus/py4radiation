#!/usr/bin/env python3

from pathlib import Path

import re
import numpy as np
import numpy.typing as npt

from py4radiation.utils.sb99_retrieve import SB99Table
from py4radiation.utils.uvb_retrieve import HM2012Table

# Physical constants
SPEED_OF_LIGHT = 2.99792458e10  # cm/s
PLANCK_EV = 4.135667696e-15  # eV s
RYDBERG_EV = 13.605693  # eV (1 Ryd)
PARSEC_TO_CM = 3.08567758e18  # cm
ANGSTROM_TO_CM = 1.0e-8  # cm


class SED:
    """
    Load, process and format spectral energy distributions for pyCIAO.

    This class handles the conversion of Leitherer et al. (1999) style
    SED tables into pyCIAO/Cloudy-readable formats.

    For scaling, consider an object of interest located at a user-specified
    distance from the radiation source.

    Parameters
    ----------
    run_name : str
        Identifier used for the output filename.
    table_id : str, optional
        Starburst99 figure identifier, e.g. '8b' or '10b'.
        Ignored if custom table is provided.
        Default is '8b'.
    table : str, Path or None, optional
        Path to a custom SED table containing two columns:
        [1] wavelength in Angstroms
        [2] log10 luminosity in erg s^-1 Angstrom^-1.
        If None, retrieve the specified Starburst99 table.
    distance_kpc : float, optional
        Distance from the radiation source in kiloparsecs.
        Default is 1.0.
    age_myr : int, optional
        Stellar population age in Myr. Used to select the
        corresponding Starburst99 column. Ignored for custom
        tables.
        Default is 3.
    sfr_msun_yr : float or None, optional
        Star formation rate in solar masses per year,
        this parameter scales the SED of continuous star
        formation models.
    mass_msun: float or None, optional
        Initial mass in solar masses, this parameter
        scales the SED of instantaneous star formation models.
    sb99_path : string, Path or None, optional
        Path to a locally stored Starburst99 model.

    Attributes
    ----------
    run_name : str
        Identifier used for the output files.
    table_id : str or None
        Starburst99 figure identifier.
    distance_kpc : float
        Distance from the radiation source in kiloparsecs.
    distance_cm : float
        Distance from the radiation source in centimetres.
    data_table : numpy.ndarray
        SED table with wavelengths in the first column.
    age_myr : int
        Requested stellar population age.
    redshift : str
        Redshift identifier, currently fixed at z = 0.

    References
    ----------
    Leitherer, C., et al. (1999), ApJS, 123, 3.
    """

    def __init__(
        self,
        run_name: str,
        table_id: str = "8b",
        table: str | Path | None = None,
        distance_kpc: float = 1.0,
        age_myr: int = 3,
        sfr_msun_yr: float | None = None,
        mass_msun: float | None = None,
        sb99_path: str | Path | None = None,
        hm12_path: str | Path | None = None,
    ) -> None:

        if not run_name or "/" in run_name or "\\" in run_name:
            raise ValueError("run_name must be a non-empty filename identifier.")

        if not np.isfinite(distance_kpc) or distance_kpc <= 0:
            raise ValueError("distance_kpc must be a positive, finite number.")

        if table is not None and sb99_path is not None:
            raise ValueError("Specify either a custom SED (table) or a local Starburst99 table (sb99_path), not both.")

        self._hm12 = table is None and table_id.upper() == "HM12"

        if self._hm12:
            if sb99_path is not None:
                raise ValueError("sb99_path cannot be used with H&M2012.")

            if sfr_msun_yr is not None or mass_msun is not None:
                raise ValueError("H&M2012 does not support SFR or mass scaling.")

        elif hm12_path is not None:
            raise ValueError("hm12_path requires table_id='HM12'.")

        self.run_name = run_name
        self.redshift = "0.0000e+00"
        self.age_myr  = age_myr

        self.distance_kpc = distance_kpc
        self.distance_cm = distance_kpc * 1e3 * PARSEC_TO_CM

        self._custom_table = table is not None
        self.table_id = None if self._custom_table else table_id

        self.sfr_msun_yr = None
        self.mass_msun = None
        self._luminosity_scale = 1.0

        if self._custom_table:
            if sfr_msun_yr is not None or mass_msun is not None:
                raise ValueError("SFR and stellar mass scaling are only supported for Starburst99 models.")

            self.data_table = np.loadtxt(Path(table).expanduser(), ndmin=2)
        elif self._hm12:
            hm12 = HM2012Table(path=hm12_path)
            self.data_table = hm12.load_uvbtable_z()
        else:
            match = re.fullmatch(r"(7|8|9|10|11|12)[a-e]", self.table_id)

            if match is None:
                raise ValueError(f"Unsupported Starburst99 table: {self.table_id}. Expected a stellar-only model from Figures 7-12.")

            figure = int(match.group(1))

            if figure in (8, 10, 12):
                if mass_msun is not None:
                    raise ValueError("Figure {figure} is a continuous star-formation model. Specify sfr_msun_yr instead of mass_msun.")

                sfr = 1.0 if sfr_msun_yr is None else float(sfr_msun_yr)

                if not np.isfinite(sfr) or sfr <= 0:
                    raise ValueError("sfr_msun_yr must be positive and finite.")

                self.sfr_msun_yr = sfr
                self._luminosity_scale = sfr / 1.0

            else:
                if sfr_msun_yr is not None:
                    raise ValueError("Figure {figure} is an instantaneous-burst model. Specify mass_msun instead of sfr_msun_yr.")

                mass = 1e6 if mass_msun is None else float(mass_msun)

                if not np.isfinite(mass) or mass <=0:
                    raise ValueError("mass_msun must be positive and finite.")

                self.mass_msun = mass

                self._luminosity_scale = mass / 1e6

            if sb99_path is not None:
                sb99_path = Path(sb99_path).expanduser().resolve()

                if not sb99_path.is_file():
                    raise FileNotFoundError(f"Starburst99 table not found: {sb99_path}")

            sb99 = SB99Table(figure=table_id, path=sb99_path)
            self.data_table = sb99.load_sb99table()

        if (self.data_table.ndim != 2 or self.data_table.shape[0] < 2 or self.data_table.shape[1] < 2):
            raise ValueError("SED tables must contain at least two rows and two columns.")

        if self._custom_table or self._hm12:
            if self.data_table.shape[1] != 2:
                raise ValueError("Custom SED tables must contain exactly two columns: wavelength and log10 luminosity.")

            self._age_column_idx = 1
        else:
            self._age_column_idx = self._map_age(age_myr)

        wavelength = self.data_table[:, 0]
        spectrum = self.data_table[:, self._age_column_idx]

        if not np.all(np.isfinite(wavelength)) or np.any(wavelength <= 0):
            raise ValueError("SED wavelengths must be positive and finite")

        if not np.all(np.isfinite(spectrum)):
            raise ValueError("SED log-luminosities must be finite.")

        if self._hm12 and np.any(spectrum <= 0):
            raise ValueError("H&M2012 intensities must be positive.")

    def _map_age(self, age: int) -> int:
        """
        Map stellar population age to a Starburst99 column.

        The mapping assumes the original age sequence:
        1-20 Myr in steps of 1 Myr,
        30-100 Myr in steps of 10 Myr,
        and 200-900 Myr in steps of 100 Myr.

        Parameters
        ----------
        age : int
            Stellar population age in Myr.

        Returns
        -------
        int
            Column index corresponding to the requested age.

        Raises
        ------
        ValueError
            If the age is unsupported or its column is absent.
        """
        ages = (list(range(1, 21)) + list(range(30, 101, 10)) + list(range(200, 901, 100)))

        age_to_column = {value: idx for idx, value in enumerate(ages, start=1)}

        if age not in age_to_column:
            raise ValueError(
                f"Unsupported Starburst99 age: {age} Myr. "
                f"Available ages: {ages}"
            )

        idx = age_to_column[age]

        if idx >= self.data_table.shape[1]:
            raise ValueError(
                f"Age {age} Myr corresponds to column {idx}, "
                f"but the table contains only "
                f"{self.data_table.shape[1]} columns."
            )

        return idx

    def get_sed(self) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Calculates Energy (Ryd) and Specific flux (F_nu).

        Returns
        -------
        energy_ryd : np.ndarray
            Photon energies in Rydbergs.
        F_nu : np.ndarray
            Specific flux F_nu in erg s^-1 cm^-2 Hz^-1
        """

        wavelength_angstrom = self.data_table[:, 0]
        wavelength_cm = wavelength_angstrom * ANGSTROM_TO_CM

        frequency = SPEED_OF_LIGHT / wavelength_cm
        energy_ryd = frequency * PLANCK_EV / RYDBERG_EV

        if self._hm12:
            j_nu = self.data_table[:, 1]

            return energy_ryd, 4.0 * np.pi * j_nu

        log_luminosity = self.data_table[:, self._age_column_idx] + np.log10(self._luminosity_scale)
        luminosity_lambda = 10**log_luminosity

        c_angstrom_s = SPEED_OF_LIGHT * 1e8
        luminosity_nu = luminosity_lambda * (wavelength_angstrom**2) / c_angstrom_s
        f_nu = luminosity_nu / (4 * np.pi * self.distance_cm**2)

        if not np.all(np.isfinite(f_nu)) or np.any(f_nu <= 0):
            raise ValueError("Calculated SED contains non-positive or non-finite fluxes.")

        return energy_ryd, f_nu

    def write_outfile(self, output_dir: str | Path = ".") -> Path:
        """
        Write a pyCIAO/Cloudy-readable input file.

        Parameters
        ----------
        output_dir : str or Path
            Directory where the output file will be saved.
            Default is the current working directory.

        Returns
        -------
        Path
            Path to the generated file.

        Raises
        ------
        ValueError
            If SED coverage does not include 1 Ryd
            or contains duplicate energy values.
        """
        energy, f_nu = self.get_sed()
        order = np.argsort(energy)

        energy = energy[order]
        f_nu   = f_nu[order]

        if self._hm12:
            duplicates = np.flatnonzero(np.diff(energy) == 0)
            energy[duplicates] *= 1.0 - 1.0e-6

        if np.any(np.diff(energy) <= 0):
            raise ValueError("SED photon energies must be strictly increasing.")

        if not (energy[0] <= 1.0 <= energy[-1]):
            raise ValueError("SED energy range must include 1 Ryd.")

        log_f_nu = np.log10(f_nu)

        norm_val = np.interp(0.0, np.log10(energy), log_f_nu)

        filename = f"{self.run_name}_z{self.redshift}.out"

        outpath = Path(output_dir).expanduser() / filename
        outpath.parent.mkdir(parents=True, exist_ok=True)

        if self._hm12:
            source_description = "H&M2012 UV/X-Ray background at z=0"
            normalisation_description = "# Quasars + galaxies"
        elif self._custom_table:
            source_description = "Custom SED"
            normalisation_description = "# User-provided luminosity"
        else:
            source_description = (f"Starburst99 SED fig{self.table_id} at {self.age_myr} Myr")

            if self.sfr_msun_yr is not None:
                normalisation_description = (f"# SFR = {self.sfr_msun_yr:.6g} Msun yr^-1")
            else:
                normalisation_description = (f"# Initial stellar mass = {self.mass_msun:.6g} Msun")

        lines = [
            f"# {source_description}",
            normalisation_description,
        ]

        if not self._hm12:
            lines.append( f"# Distance = {self.distance_kpc} kpc")

        lines.extend([
             f"# z = {self.redshift}",
            "# E [Ryd] log10 (F_nu)"
        ])

        for idx, (e, log_flux) in enumerate(zip(energy, log_f_nu, strict=True)):
            command = "interpolate" if idx == 0 else "continue"

            lines.append(f"{command} ({e:.10f} {log_flux:.10f})")

        lines.append(f"f(nu) = {norm_val:.14f} at 1.0 Ryd")
        if self._hm12:
            lines.append("illuminate isotropic")
        lines.append("")

        with open(outpath, "w") as f:
            f.write("\n".join(lines))

        return outpath
