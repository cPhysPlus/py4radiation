#!/usr/bin/env python3

from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
import requests
from platformdirs import user_cache_dir

class HM2012Table:
    URL = "https://www.ucolick.org/~pmadau/CUBA/Media/UVB.out"

    def __init__(self, path: str | Path | None = None) -> None:
        self.local = path is not None
        self.path = (Path(path).expanduser() if path is not None else Path(user_cache_dir("py4radiation")) / "UVB.out")

    def get_uvbtable(self) -> Path:
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
