#!/usr/bin/env python3

"""
Check that heating/cooling maps keep their physical coordinates
"""

import pytest
import numpy as np

from py4radiation import HeatingCoolingTables

def test_heating_cooling_table(run_directory):
    temperatures = np.array([1e3, 1e4, 1e5])
    expected = []

    for run_id, log_density in enumerate((-3.0, -2.0), start=1):
        heating = run_id * np.array([1e-22, 2e-22, 3e-22])
        cooling = 2.0 * heating
        mmw = np.full(3, 1.0 + run_id / 10)

        map_data = np.column_stack((temperatures, heating, cooling,mmw))
        np.savetxt(run_directory / f"demo_run{run_id}.dat", map_data)

        expected.append(np.column_stack((np.full(3, 10**log_density), map_data)))

    processor = HeatingCoolingTables(run_directory, "demo")
    result_path = processor.write_table(outdir=run_directory)

    actual = np.loadtxt(result_path, skiprows=1)

    np.testing.assert_allclose(actual, np.vstack(expected), rtol=1e-7, atol=0)

    # Inconsistent temperature grids must be rejected
    # without replacing the existing valid table
    original_output = result_path.read_bytes()

    bad_data = np.loadtxt(run_directory / "demo_run2.dat")
    bad_data[-1, 0] = 2e5

    np.savetxt(run_directory / "demo_run2.dat", bad_data)

    with pytest.raises(ValueError, match="Inconsistent temperature grid"):
        processor.write_table(outdir=run_directory)

    assert result_path.read_bytes() == original_output
