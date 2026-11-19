Tutorials
=========

The py4radiation tutorials show the complete workflow,
from preparing radiation spectra to processing Cloudy outputs.

The notebooks include executed code cells, scientific figures
and numerical results. They can be viewed directly on GitHub.

The associated input files and reference outputs are provided
in the notebooks directory.


01. Preparing and comparing radiation spectra
---------------------------------------------

This tutorial introduces the SED class and its principal
scientific conventions. It shows:

* Starburst99 stellar continua.
* Scaling by star-formation rate and initial stellar mass.
* Inverse-square distance scaling.
* The HM2012 UV/X-ray background.
* Preparing Cloudy-compatible continuum files.

`Open notebook 01 on GitHub
<https://github.com/cPhysPlus/py4radiation/blob/main/notebooks/01_preparing_spectra.ipynb>`_


02. Preparing and running Cloudy calculations
---------------------------------------------

This tutorial demonstrates how to prepare Cloudy parameter
files and execute photoionisation calculations using pyCIAO.
It shows:

* Density and temperature grids.
* Heating/cooling and ionisation calculation modes.
* Python multiprocessing and MPI.
* Cloudy output files and run metadata.

`Open notebook 02 on GitHub
<https://github.com/cPhysPlus/py4radiation/blob/main/notebooks/02_cloudy_calculations.ipynb>`_


03. Processing heating, cooling and ionisation tables
-----------------------------------------------------

This tutorial demonstrates how to process Cloudy outputs
into numerical tables for astrophysical applications.
It shows:

* Radiative heating and cooling coefficients.
* Mean molecular weights.
* HDF5 ionisation-fraction tables.
* Table dimensions, coordinates and metadata.
* Visualisation of the resulting quantities.

`Open notebook 03 on GitHub
<https://github.com/cPhysPlus/py4radiation/blob/main/notebooks/03_processing_tables.ipynb>`_


Reference data
--------------

The notebooks include numerical outputs that users can
compare against results from their own installations.

These files provide examples of the expected formats
and numerical conventions.

Comparisons should account for the Cloudy version,
radiation model and physical parameters used in each
calculation.

`Browse the notebooks and reference files on GitHub
<https://github.com/cPhysPlus/py4radiation/tree/main/notebooks>`_
