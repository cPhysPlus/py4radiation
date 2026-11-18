#!/usr/bin/env python3

import re
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
import requests
from platformdirs import user_cache_path

URL = "https://massivestars.stsci.edu/starburst99/data/"
CACHE_DIR = user_cache_path("py4radiation", appauthor=False)  / "starburst99"

class SB99Table:
    """
    Retrieve and load pre-computed Starburst99 tables.

    This class provides access to the original Starburst99 dataset
    presented by Leitherer et al. (1999).

    Figures 1-12 contain spectral energy distributions (SEDs).
    Figures 7-12 include stellar emission only, they are recommended
    as input spectra for photoionisation models.

    Tables are downloaded on demand and stored in a local cache
    to avoid repeated downloads.

    Parameters
    ----------
    figure: str
            Figure identifier from Leitherer et al. (1999), e.g. '8a'.
            The corresponding filename is constructed as 'fig8a.dat'.
    path : str, Path or None, optional
            Destination file path. If None, use the default cache
            directory provided by platformdirs.
    refresh: bool, optional
            If True, download a fresh copy of the table on the next
            retrieval, even if a cached copy exists.
            Default is False.

    Attributes
    ----------
    figure : str
        Figure identifier.
    path : Path
        Absolute path to the local table.
    url : str
        URL of the corresponding Starburst99 table.

    References
    ----------
    Leitherer, C., et al. (1999), ApJS, 123, 3.

    Examples
    --------
    >>> table = SB99Table("8a")
    >>> path = table.get_sb99table()
    >>> data = table.load_sb99table()
    """

    def __init__(self, figure: str, path: str | Path | None = None, refresh: bool = False) -> None:
        figure = figure.strip().lower()

        if not re.fullmatch(r"(?:[1-9]|1[0-2])[a-z]", figure):
            raise ValueError(f"Invalid figure identifier: {figure!r}. Expected a value such as '8a'.")

        self.figure = figure
        self.filename = f"fig{figure}.dat"
        self.url = URL + self.filename

        if path is None:
            path = CACHE_DIR / self.filename

        path = Path(path).expanduser().resolve()

        self.path = path
        self._refresh = refresh

    def get_sb99table(self) -> Path:
        """
        Retrieve the Starburst99 table.

        Return the cached table if available. Otherwise, download
        the file from the Starburst99 website.

        Downloads are written to a temporary file before replacing
        the destination to avoid leaving incomplete files.

        Returns
        -------
        Path
            Absolute path to the downloaded table.

        Raises
        ------
        requests.RequestException
            If the download fails.
        OSError
            If the file cannot be written to the destination.
        """
        if self.path.is_file() and not self._refresh:
            return self.path

        self.path.parent.mkdir(parents=True, exist_ok=True)

        with NamedTemporaryFile(dir=self.path.parent, delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            with requests.get(self.url, stream=True, timeout=(5, 30)) as response:
                response.raise_for_status()

                content_type = response.headers.get(
                    "Content-Type", ""
                ).lower()

                if "text/html" in content_type:
                    raise ValueError(
                        f"Expected a data file, but received HTML "
                        f"from {self.url}"
                    )

                with tmp_path.open("wb") as file:
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            file.write(chunk)

                if tmp_path.stat().st_size == 0:
                    raise ValueError(f"Downloaded an empty file from {self.url}")

            tmp_path.replace(self.path)

        finally:
            tmp_path.unlink(missing_ok=True)

        self._refresh = False

        return self.path

    def load_sb99table(self, skiprows: int = 3) -> np.ndarray:
        """
        Load a Starburst99 table into a NumPy array.

        Retrieve the table from the local cache, downloading it
        if necessary, and load its contents.

        The default settings assume the format of the original
        Starburst99 SED tables (Figures 1-12), which contain
        three header lines.

        Parameters
        ----------
        skiprows: int, optional
            Number of header lines  to skip.
            Default is 3.

        Returns
        -------
        numpy.ndarray
            Transposed table, with each original column stored
            in a row. For SED tables, the first row contains
            wavelengths and the remaining rows contain the
            spectra at different stellar population ages.

        Notes
        -----
        Other Starburst99 tables may require different parsing
        settings.
        """
        table_path = self.get_sb99table()

        return np.loadtxt(str(table_path), skiprows=skiprows)
