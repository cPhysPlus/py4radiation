# py4radiation

![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)
![Python](https://img.shields.io/badge/python->=3.11-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

A modern, modular Python toolkit designed to process and format outputs from pyCIAO simulations. This package provides streamlined pipelines for generating Spectral Energy Distributions (SEDs), Heating/Cooling tables, and Ion Fraction maps for astrophysical HD/MHD codes.

---

## Features

* **Heating & Cooling Consolidation:** Automatically reads pyCIAO run files to generate consolidated tables mapping temperature, mean molecular weight, heating, and cooling.
* **Ion Fraction Processing:** Consolidates distributed ion fraction maps into efficient, highly structured HDF5 files.
* **CIAOLoop Integration:** Generates perfectly formatted parameter (`.par`) files for coarse or fine grid resolutions.
* **SED Formatting:** Converts Leitherer et al. (1999) style tables into Cloudy-readable formats.

---

## Installation

It is highly recommended to install this package in editable mode during development. This ensures that any modifications to the source scripts are instantly available without requiring reinstallation.

Run the following command from the repository root (where `pyproject.toml` is located):

```bash
python -m pip install -e .