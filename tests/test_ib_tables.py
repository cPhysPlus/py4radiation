#!/usr/bin/env python3

"""
Check HDF5 axis order, coordinates and z = 0 duplication
"""

import h5py
import numpy as np

from py4radiation import IonTables

def test_ionisation_hdf5(run_directory):
    log_temperature = np.array([1e3, 1e4, 1e5])
    expected = []

    for run_id in (1, 2):
        values = np.column_stack((-0.1 * run_id - 0.01 * np.arange(3), -0.5 * run_id - 0.02 * np.arange(3)))
        expected.append(values)
        np.savetxt(run_directory / f"demo_run{run_id}_H.dat", np.column_stack((log_temperature, values)))

    tables = IonTables(run_dir=run_directory, run_name="demo", elements="H")
    tables.write_table()

    with h5py.File(tables.outfile) as stream:
        hydrogen = stream["H"]

        # ion stage, density, redshift, temperature
        assert hydrogen.shape == (2, 2, 2, 3)

        np.testing.assert_array_equal(hydrogen.attrs["Parameter1"], [-3, -2])
        np.testing.assert_array_equal(hydrogen.attrs["Parameter2"], [0, 1e-4])
        np.testing.assert_array_equal(hydrogen.attrs["Temperature"], log_temperature)

        for i in range(2):
            # original values at z = 0
            np.testing.assert_allclose(hydrogen[:, i, 0, :], expected[i].T, rtol=1e-12, atol=0)

            # second redshift must be equal
            np.testing.assert_array_equal(hydrogen[:, i, 1, :], hydrogen[:, i, 0, :])
