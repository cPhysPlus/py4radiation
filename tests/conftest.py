#!/usr/bin/env python3

"""
Ofline input files shared by the five tests.
"""

import pytest
import numpy as np

@pytest.fixture
def sb99_file(tmp_path):
    """
    Three wavelengths and three distinct Starburst99 age columns.
    """
    wavelength = [500.0, 1000.0, 2000.0]
    table = np.column_stack((wavelength, np.tile([29.0, 30.0, 31.0], (3, 1))))

    path = tmp_path / "fig8b.dat"

    with path.open("w") as stream:
        stream.write(
            "# Synthetic Starburst99 SED\n"
            "# Wavelength and log luminosity\n"
            "# Test only\n"
        )

        np.savetxt(stream, table)

    return path

@pytest.fixture
def uvb_file(tmp_path):
    """
    Synthetic z=0 intensity table with a duplicated wavelength.
    """
    wavelength_1ryd = 2.99792458e10 * 4.135667696e-15 / (13.605693e-8)

    wavelength = [500.0, 500.0, wavelength_1ryd, 2000.0]
    j_nu = np.array((2e-24, 3e-24, 1e-23, 5e-24))

    path = tmp_path / "UVB.out"

    with path.open("w") as stream:
        stream.write("# Synthetic UV background\n0.0 1.0\n")

        np.savetxt(stream, np.column_stack((wavelength, j_nu, 2 * j_nu)))

    return path

@pytest.fixture
def run_directory(tmp_path):
    """
    Two density runs and one z=0 radiation-field loop.
    """
    (tmp_path / "demo.run").write_text(
        "# Loop commands and values:\n"
        "# hden: -3 -2\n"
        '# init "demo_z*.out": 0.0000e+00\n'
        "#\n"
        '#run\thden\tinit "demo_z*.out"\n'
        "1\t-3\t0.0000e+00\n"
        "2\t-2\t0.0000e+00\n",
        encoding="utf-8"
    )

    return tmp_path
