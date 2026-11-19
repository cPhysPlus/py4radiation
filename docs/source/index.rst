Welcome to py4radiation!
========================

.. container:: landing-intro

   **Radiation-field preparation and Cloudy workflows
   for astrophysical simulations.**

   py4radiation is a modular Python framework for preparing
   custom spectral energy distributions (SEDs), executing Cloudy
   photoionisation calculations, and processing radiative
   heating, cooling and ionisation data for astrophysical
   hydrodynamic and magnetohydrodynamic simulations.

Overview
--------

The workflow consists of:

**01 — Prepare spectra**

Retrieve and prepare Starburst99 SEDs, the Haardt & Madau (2012)
UV/X-ray background, or user-prepared SEDs. Apply the relevant
physical scaling and convert the spectra into Cloudy-readable
input files.

**02 — Execute Cloudy**

Configure and execute photoionisation calculations with
pyCIAO, using Python multiprocessing or MPI.

**03 — Process results**

Assemble heating/cooling tables and HDF5 ion fraction tables
from Cloudy outputs.


Getting started
---------------

New users should begin with the :doc:`installation` guide
and :doc:`quickstart`.

The :doc:`tutorials` page provides three executed Jupyter
notebooks covering the complete workflow, including figures,
numerical results and reference data.

For detailed information about individual classes and
methods, consult the :doc:`modules`.


Scientific conventions
----------------------

py4radiation prepares existing radiation models rather
than calculating stellar populations or synthesising the
metagalactic background.

For photoionisation calculations, the package uses the
stellar-only spectra from Starburst99 Figures 7-12.

For HM2012, the tabulated specific intensity is represented
by the angle-integrated quantity. This quantity has the same
units as the stellar spectral flux density, but it is not the
directional flux of an isotropic radiation field.


Documentation
-------------

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   installation
   quickstart
   tutorials

.. toctree::
   :maxdepth: 2
   :caption: Reference and Development

   modules
   testing
   citation
