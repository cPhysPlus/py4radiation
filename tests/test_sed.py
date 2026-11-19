#!/usr/bin/env python3

"""
Physical conversions made when preparing input spectra.
"""

import numpy as np
from py4radiation import SED
from py4radiation.utils.uvb_retrieve import HM2012Table

def test_spectral_preparation(sb99_file, uvb_file, tmp_path):
    # Continuous SFR, burst mass, distance, and age column selection
    cases = [
        ("8b", "sfr_msun_yr", 1.0, 5.0, 5.0),
        ("7b", "mass_msun", 1e6, 5e6, 5.0),
        ("8b", "distance_kpc", 1.0, 5.0, 1 / 25),
        ("8b", "age_myr", 1, 3, 100.00)
    ]

    for figure, parameter, first, second, ratio in cases:
        shared = {"table_id": figure, "sb99_path": sb99_file}

        a = SED("a", **shared, **{parameter: first})
        b = SED("b", **shared, **{parameter: second})

        energy_a, flux_a = a.get_sed()
        energy_b, flux_b = b.get_sed()

        np.testing.assert_allclose(energy_a, energy_b, rtol=0, atol=0)
        np.testing.assert_allclose(flux_b / flux_a, ratio, rtol=1e-12, atol=0)

    # Independently calculate following
    # L_lambda -> L_nu -> F_nu

    c = 2.99792458e10 # cm s^-1
    h = 4.135667696e-15 # eV s
    ryd = 13.605693 # eV
    pc = 3.08567758e18 # cm

    wvl_1ryd = c * h / (ryd * 1e-8)
    wavelength = np.array([500.0, wvl_1ryd, 2000.0])

    custom = tmp_path / "custom.dat"
    np.savetxt(custom, np.column_stack((wavelength, np.full(3, 30.0))))

    sed = SED("custom", table=custom, distance_kpc=2.0)
    energy, flux = sed.get_sed()

    d_cm = 2e3 * pc

    expected_energy = c * h / (wavelength * 1e-8 * ryd)
    expected_flux   = (1e30 * wavelength**2 / (c * 1e8)) / (4 * np.pi * d_cm**2)

    np.testing.assert_allclose(energy, expected_energy, rtol=1e-12, atol=0)
    np.testing.assert_allclose(flux, expected_flux, rtol=1e-12, atol=0)

    # HM2012, original J_nu must be converted into 4 * pi * J_nu
    original = HM2012Table(path=uvb_file).load_uvbtable_z()

    hm12 = SED("hm12", table_id="HM12", hm12_path=uvb_file)
    hm12_far = SED("hm12_far", table_id="HM12", hm12_path=uvb_file, distance_kpc=5.0)

    _, hm12_flux = hm12.get_sed()

    np.testing.assert_allclose(hm12_flux, 4 * np.pi * original[:, 1], rtol=1e-12, atol=0)

    # HM2012 must not depend on distance
    np.testing.assert_allclose(hm12_far.get_sed()[1], hm12_flux, rtol=0, atol=0)

    # Duplicate wavelengths must not produce duplicate Cloudy energies
    lines = hm12.write_outfile(tmp_path).read_text().splitlines()
    entries = [line for line in lines if line.startswith(("interpolate ", "continue "))]

    written_energy = [float(line.split("(")[1].split()[0]) for line in entries]
    assert np.all(np.diff(written_energy) > 0)

    norm = float(next(line.split()[2] for line in lines if line.startswith("f(nu) =")))
    np.testing.assert_allclose(norm, np.log10(4 * np.pi * 1e-23), atol=1e-10, rtol=0)
