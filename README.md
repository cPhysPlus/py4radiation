# py4radiation

![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**D. Villarruel-Yanez, W.E. Banda-Barragan & B. Casavecchia (in prep.)**

**py4radiation** is a modular Python framework designed to generate radiative heating/cooling rates and ionisation fractions from spectral energy distributions (SEDs). The package provides an integrated workflow for preparing radiation fields, executing photo-ionisation calculations with Cloudy, and processing the resulting data into tables suitable for coupling with simulation codes and post-processing packages.

## Features

- **Starburst99 retrieval script:** Download and cache Starburst99 tables on demand, with support for local files in offline environments.
- **Haardt & Madau (2012) UV/X-ray background retrieval script:** Download and cache the meta-galactic background with support for the local table in offline environments.
- **Stellar population scaling:** Scale Starburst99 luminosities according to the star-formation rate (continuous star formation) or initial stellar mass (instantaneous bursts).
- **Cloudy integration:** Generate configuration files and execute photoionisation calculations through pyCIAO and Cloudy.
- **Parallel execution:** Distribute Cloudy calculations using Python `multiprocessing` or `mpi4py` with the MPI library.
- **Heating and cooling tables:** Process radiative heating/ cooling rates and mean particle mass into tables for HD/MHD simulations.
- **Ion fractions:** Generate HDF5 ionisation tables.

## Supported radiation fields:

## Starburst99 UV backgrounds:

Following the recommendations of Leitherer et al. (1999), **py4radiation** uses Starburst99 Figures 7-12 for photoionisation calculations. These models contain the stellar continuum only, whereas Figures 1-6 also include nebular continuum emission. Using stellar-only spectra avoids potential double-counting of nebular radiation, which is calculated self-consistently by Cloudy.

## Haardt & Madau (2012) UV/X-ray background

**py4radiation** also supports the Haardt & Madau (2012) ultraviolet/X-ray background (HM2012) at redshift $z=0$. The original table provides the specific intensity $J_{\nu}$ in erg s $^{-1}$ cm $^{-2}$ Hz $^{-1}$ sr $^{-1}$. For consistency with the stellar SEDs, the package converts $J_nu$ into the specific flux in erg s $^{-1}$ cm $^{-2}$ Hz $^{-1}$:

$$
    F_{\nu,\mathrm{equiv}} = 4\pi J_{\nu}
$$

This allows the stellar and metagalactic radiation fields to be compared using the same spectral units and provides the correct normalisation for Cloudy. $F_{\nu}$ represents the angle-integrated intensity, not the directional flux of an isotropic radiation field.

## Requirements

- Python 3.11 or newer.
- Cloudy (Ferland et al. 2013), installed separately, for photoionisation calculations.
- A compatible MPI implementation for MPI-based execution (optional).

Cloudy is not distributed with **py4radiation** and must be installed independently. The package can be used to process existing simulation outputs without executing Cloudy. We recommend version C13.05.

Starburst99 tables are also not distributed with the package. They can be downloaded automatically when needed or provided as local files.

## Installation

To install **py4radiation** from source, navigate to the repository root (where `pyproject.toml` is located) and run:

```bash
python -m pip install .
```

### Development installation

For development, an editable installation is recommended:

```bash
python -m pip install -e .
```

This allows modifications to the Python source code to take effect without reinstalling the package.

### Optional MPI support

MPI support is available as an optional dependency for the `pyciao` component.

To install **py4radiation** with MPI support:

```bash
python -m pip install ".[mpi]"
```

For an editable installation with MPI support:

```bash
python -m pip install -e ".[mpi]"
```

A compatible MPI implementation must also be available on the system.

## Quick Start

### Using a Starburst99 SED

The `SED` class generates Cloudy-readable radiation fields from Starburst99 models or user-provided spectra.

For continuous star formation models (Figures 8, 10 and 12), the luminosity can be scaled using the star-formation rate:

```python
from py4radiation import SED

sed = SED(
    run_name="continuous_sf",
    table_id="8b",
    sfr_msun_yr=5.0,
    distance_kpc=1.0,
    age_myr=3,
)

sed.write_outfile()
```

For instantaneous starburst models (Figures 7, 9 and 11), the luminosity can be scaled using the initial stellar mass:

```python
sed = SED(
    run_name="stellar_cluster",
    table_id="7b",
    mass_msun=1e6,
    distance_kpc=1.0,
    age_myr=3,
)

sed.write_outfile()
```

The reference Starburst99 models assume a constant star-formation rate of 1 solar mass per year or an initial stellar mass of 10^6 solar masses, respectively.

### Using local Starburst99 tables

On systems without internet access, such as air-gapped HPC environments, a local Starburst99 table can be supplied directly:

```python
sed = SED(
    run_name="offline_model",
    table_id="8b",
    sb99_path="/path/to/fig8b.dat",
    sfr_msun_yr=5.0,
    distance_kpc=1.0,
    age_myr=3,
)

sed.write_outfile()
```

The same stellar population scaling is applied without requiring an internet connection.

### Using a custom SED

Users may also provide a two-column spectrum containing wavelength (Angstroms) and logarithmic spectral luminosity (erg s^-1 Angstrom^-1):

```python
sed = SED(
    run_name="custom_model",
    table="custom_sed.dat",
    distance_kpc=1.0,
)

sed.write_outfile()
```

In this case, the supplied luminosities are used directly, without Starburst99 scaling.

## pyCIAO

**pyCIAO** provides an interface for executing Cloudy calculations using Python multiprocessing or MPI.

It supports the generation of radiative heating and cooling maps and ionisation-fraction maps over user-defined physical parameter grids.

Once a parameter file has been generated, calculations can be executed using:

```bash
python -m py4radiation.pyciao.pyciao model.par --nproc 4
```

MPI-based execution is also supported when the optional MPI dependencies and a compatible MPI environment are available.

The resulting calculations can be processed using `HeatingCoolingTables` and `IonTables` to generate tables for astrophysical simulation and analysis tools.

## Tutorials

The [`notebooks/`](notebooks/) directory contains worked examples
demonstrating how to prepare radiation spectra, perform Cloudy
calculations, and process the resulting tables.

The notebooks include figures and numerical outputs so that
the examples can be explored directly on GitHub without
executing the calculations.

- [Preparing and comparing radiation spectra](notebooks/01_preparing_spectra.ipynb)
- [Preparing and running Cloudy calculations](notebooks/02_cloudy_calculations.ipynb)
- [Processing heating, cooling and ion tables](notebooks/03_processing_tables.ipynb)

## Citation

**py4radiation** is introduced in:

D. Villarruel-Yanez, W. E. Banda-Barragan & B. Casavecchia (in preparation).

If you use this package in your research, please cite the associated publication once available.

## Licence

This project is distributed under the MIT licence. See the [LICENSE](LICENSE) file for details.
