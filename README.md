# py4radiation

![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**D. Villarruel-Yanez, W.E. Banda-Barragan & B. Casavecchia (2026)**

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

Following the recommendations of Leitherer et al. (1999), **py4radiation** uses [Starburst99 Figures 7-12](https://massivestars.stsci.edu/starburst99/docs/table-index.html) for photo-ionisation calculations. These models contain the stellar continuum only, whereas Figures 1-6 also include nebular continuum emission. Using stellar-only spectra avoids potential double-counting of nebular radiation, which is calculated self-consistently by Cloudy.

## Haardt & Madau (2012) meta-galactic UV/X-ray background:

**py4radiation** also supports the Haardt & Madau (2012) ultraviolet/X-ray background (HM2012) at redshift $z=0$. The original table provides the specific intensity $J_{\nu}$ in erg s $^{-1}$ cm $^{-2}$ Hz $^{-1}$ sr $^{-1}$. For consistency with the stellar SEDs, the package converts $J_nu$ into the specific flux in erg s $^{-1}$ cm $^{-2}$ Hz $^{-1}$:

$$
    F_{\nu,\mathrm{equiv}} = 4\pi J_{\nu}
$$

This allows the stellar and metagalactic radiation fields to be compared using the same spectral units and provides the correct normalisation for Cloudy. $F_{\nu}$ represents the angle-integrated intensity, not the directional flux of an isotropic radiation field.

## Requirements

- Python 3.11 or newer.
- [Cloudy (Ferland et al. 2013)](https://data.nublado.org/cloudy_releases/c13), installed separately, for photoionisation calculations.
- A compatible MPI implementation for MPI-based execution (optional).

### Notes:

- Starburst99 and Haardt & Madau (2012) tables are not distributed with the package. They can be downloaded automatically using the scripts provided in [`src/py4radiation/utils`](https://github.com/cPhysPlus/py4radiation/tree/main/src/py4radiation/utils) when needed or provided as local files.

- Cloudy is not distributed with py4radiation and must be installed independently. We recommend [version C13.05](https://data.nublado.org/cloudy_releases/c13).


## Installation & Documentation:

The user is referred to the [code documentation](https://py4radiation.readthedocs.io) for details on:

- **Installation:** https://py4radiation.readthedocs.io/en/latest/installation.html
- **Quickstart:** https://py4radiation.readthedocs.io/en/latest/quickstart.html
- **Tutorials:** https://py4radiation.readthedocs.io/en/latest/tutorials.html

## Catalogue: 

This [dataset repository](https://github.com/cPhysPlus/heating-cooling-ion-tables) provides ready-to-use datasets generated with py4radiation, including:

- **Heating and cooling functions in ASCII format:** these can be readily coupled to any existing hydrodynamic code, like [PLUTO/gPLUTO](https://plutocode.ph.unito.it).
  
- **Ion fraction tables in HDF5 format:** these can be readily coupled to post-processing tools, like [Trident](https://github.com/trident-project/trident).

## Tutorials:

The [`notebooks/`](notebooks/) directory contains worked examples demonstrating how to prepare radiation spectra, perform Cloudy calculations, and process the resulting tables.

The notebooks include figures and numerical outputs so that the examples can be explored directly on GitHub without executing the calculations.

- [Preparing and comparing radiation spectra](notebooks/01_preparing_spectra.ipynb)
- [Preparing and running Cloudy calculations](notebooks/02_cloudy_calculations.ipynb)
- [Processing heating, cooling and ion tables](notebooks/03_processing_tables.ipynb)
- [Reading the catalogue datasets: heating/cooling/ion tables](notebooks/04_tables_catalogue.ipynb)

## Citation

If you use `py4radiation` in your research, please cite our paper:

Villarruel-Yánez, D., Banda-Barragán, W. E., & Casavecchia, B. (2026).
*py4radiation: a framework for generating heating/cooling functions and ion fractions from custom radiation fields for astrophysical simulations*.
arXiv:2611.29772.
https://doi.org/10.48550/arXiv.2611.29772

The citation is also available in [BibTeX format](CITATION.bib).

## Licence

This project is distributed under the MIT licence. See the [LICENSE](LICENSE) file for details.
