#!/usr/bin/env python3

"""
Consistency of SED, parameter files, tasks and .run records.
"""

import numpy as np

from py4radiation import SED, ParameterFiles

from py4radiation.pyciao.parser import Config
from py4radiation.pyciao.tasks import TaskManager
from py4radiation.pyciao.pyciao import write_runfile

def test_cloudy_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # Prepare a synthetic continuum containing exactly 1 Ryd
    c = 2.99792458e10 # cm s^-1
    h = 4.135667696e-15 # eV s
    ryd = 13.605693 # eV
    pc = 3.08567758e18 # cm

    wvl_1ryd = c * h / (ryd * 1e-8)
    wavelength = np.array([500.0, wvl_1ryd, 2000.0])

    custom = tmp_path / "custom.dat"
    np.savetxt(custom, np.column_stack((wavelength, np.full(3, 30.0))))

    outfile = SED("demo", table=custom).write_outfile()
    lines = outfile.read_text().splitlines()

    values = [line for line in lines if line.startswith(("interpolate ", "continue "))]
    energies = [float(line.split("(")[1].split()[0]) for line in values]

    assert len(values) == 3
    assert np.all(np.diff(energies) > 0)

    # Verify the Cloudy normalisation at 1 Ryd
    norm = float(next(line.split()[2] for line in lines if line.startswith("f(nu) =")))

    d_cm = 1e3 * pc
    expected_flux   = (1e30 * wvl_1ryd**2 / (c * 1e8)) / (4 * np.pi * d_cm**2)
    np.testing.assert_allclose(norm, np.log10(expected_flux), atol=1e-10, rtol=0)

    # Prepare calculation modes
    par = ParameterFiles(
        cloudy_path="/nonexistent/cloudy",
        run_name="demo",
        elements="H C",
        n_limits=(-3, -2),
        n_spacing=1.0,
        T_limits=(3, 4),
        T_points=3
    )

    hc_path = par.hc_parfile()
    ib_path = par.ib_parfile()

    for par_path, mode in [(hc_path, 1), (ib_path, 3)]:
        config = Config(par_path)
        config.parse()

        assert int(config.params["cloudyRunMode"]) == mode

        tasks = list(TaskManager(config).gen_tasks())

        # Two densities, one radiation field, there must be two runs
        assert [t["run_index"] for t in tasks] == [1, 2]

        hden = [next(float(cmd.split()[1]) for cmd in t["base_commands"] if cmd.startswith("hden ")) for t in tasks]
        np.testing.assert_array_equal(hden, [-3.0, -2.0])

        assert all(any("demo_z0.0000e+00.out" in cmd for cmd in t["base_commands"]) for t in tasks)

        # The .run records must describe those same tasks
        write_runfile(config)

        subdir = "hc" if mode == 1 else "ib"
        run_path = tmp_path / subdir / "demo.run"

        rows = run_path.read_text().splitlines()

        header_index = next(i for i, line in enumerate(rows) if line.startswith("#run"))
        records = [line.split("\t") for line in rows[header_index + 1:]]
        assert [int(row[0]) for row in records] == [1, 2]
        np.testing.assert_array_equal([float(row[1]) for row in records], hden)
        assert all(float(row[2]) == 0.0 for row in records)
