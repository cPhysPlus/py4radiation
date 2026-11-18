#!/usr/bin/env python3

"""
Retrieve and load the Haardt & Madau (2012) UV/X-ray background.
"""

from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
import requests
from platformdirs import user_cache_dir

class HM2012Table:
    """
    Retrieve and load the Haardt & Madau (2012) UV/X-ray background.

    This class provides access to the CUBA ultraviolet and X-ray background
    spectrum produced by Haardt & Madau (2012), including emission from
    quasars and galaxies.

    Tables are downloaded on demand and cached locally. An existing
    file may also be supplied for use in offline environments.

    The original intensity values are returned without conversion
    to spectral flux densities. That conversion is performed
    separately by the SED class.

    Parameters
    ----------
    path : str, Path or None, optional
        Path to a locally stored UVB.out file. If None, use the
        default cache directory.

    Attributes
    ----------
    path : Path
        Location of the UV background table.
    local : bool
        True when an explicit local file was supplied.
        In this case, downloading is disabled if the file
        does not exist.

    References
    ----------
    Haardt, F. and Madau, P. (2012), ApJ, 746, 125.
    """
    URL = "https://www.ucolick.org/~pmadau/CUBA/Media/UVB.out"

    def __init__(self, path: str | Path | None = None) -> None:
        """
        Select an existing UVB file or the default cache location.
        """
        self.local = path is not None
        self.path = (Path(path).expanduser() if path is not None else Path(user_cache_dir("py4radiation")) / "UVB.out")

    def get_uvbtable(self) -> Path:
        """
        Return the HM2012 table from local or download it.

        If an explicitly supplied local file exists, return it
        without accessing the network.

        If no local path was supplied, use the cached table or
        download UVB.out into the default cache directory.

        Downloads are first written to a temporary file to avoid
        leaving incomplete data at the final destination.

        Returns
        -------
        Path
            Path to the existing or downloaded UVB.out file.

        Raises
        ------
        FileNotFoundError
            If an explicitly requested local file does not exist.
        requests.RequestException
            If the download request fails.
        OSError
            If the cached file cannot be written.
        """
        if self.path.is_file():
            return self.path

        if self.local:
            raise FileNotFoundError(f"UVB table not found: {self.path}")

        self.path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = None
        try:
            response = requests.get(self.URL, timeout=30)
            response.raise_for_status()

            with NamedTemporaryFile(dir=self.path.parent, delete=False) as tmp:
                tmp.write(response.content)
                tmp_path = Path(tmp.name)

            tmp_path.replace(self.path)

        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

        return self.path

    def load_uvbtable_z(self, redshift_col: int = 1) -> np.ndarray:
        """
        Load wavelengths and specific intensities for one redshift column.

        The original UVB.out file contains a numerical redshift header,
        followed by rows containing rest-frame wavelengths and
        specific intensities at the sampled redshifts.

        The first spectral column contains wavelengths in Angstroms.
        The remaining columns contain J_nu in
        erg s^-1 cm^-2 Hz^-1 sr^-1.

        The default redshift_col=1 selects z=0.

        Parameters
        ----------
        redshift_col : int, optional
            Zero-based column index corresponding to the desired
            redshift in each spectral data row.
            Defaults to 1, corresponding to z=0.

        Returns
        -------
        numpy.ndarray
            Two-dimensional array containing:
            - Column 0: rest-frame wavelength in Angstroms.
            - Column 1: specific intensity J_nu in
            erg s^-1 cm^-2 Hz^-1 sr^-1.

        Raises
        ------
        ValueError
            If the numerical redshift header is missing, empty,
            or does not begin at z=0.

        Notes
        -----
        The redshift_col argument selects a table column, not an
        arbitrary numerical redshift.

        The current py4radiation workflow uses the z=0 spectrum.
        """
        with self.get_uvbtable().open(encoding="utf-8") as f:
            lines = (
                line for line in f
                if line.strip() and not line.lstrip().startswith("#")
            )

            redshifts = np.fromstring(next(lines), sep=" ")

            if len(redshifts) == 0 or redshifts[0] != 0.0:
                raise ValueError("UVB table does not start with z=0.")

            data = np.loadtxt(lines, usecols=(0, redshift_col), ndmin=2)

        return data
