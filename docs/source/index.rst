Welcome to py4radiation
=======================

**py4radiation** is a modular Python framework for generating
radiative heating and cooling rates and ionisation fractions
from custom spectral energy distributions (SEDs).

The package provides an integrated workflow for preparing radiation
fields, executing photoionisation calculations with Cloudy, and
processing the resulting data into tables suitable for coupling
with astrophysical hydrodynamics (HD) and magnetohydrodynamics
(MHD) codes.


Overview
--------

The framework consists of three main components:

* **Radiation fields:** Prepare Cloudy-compatible SEDs from
  Starburst99 stellar population models, the Haardt & Madau
  (2012) UV/X-ray background, or user-provided SEDs.

* **Cloudy execution:** Prepare parameter files and perform
  photoionisation calculations using pyCIAO, with support
  for Python multiprocessing and MPI.

* **Generation of tables:** Combine Cloudy outputs into radiative
  heating/cooling tables and HDF5 ion fraction tables for
  astrophysical HD/MHD codes.

The framework supports local input files and cached reference
SEDs, allowing the preparation of radiation fields online and
offline.


Scientific considerations
-------------------------

For stellar radiation fields, py4radiation uses the stellar-only
spectra from Starburst99 Figures 7-12, following the
recommendations of Leitherer et al. (1999) for photoionisation
calculations.

For the Haardt & Madau (2012) ultraviolet background, the
tabulated specific intensity is converted into the equivalent
spectral quantity

.. math::

   F_{\nu,\mathrm{equiv}} = 4\pi J_\nu.

This convention allows the stellar and metagalactic radiation
fields to be represented using the same spectral units.

Here, :math:`4\pi J_\nu` is the angle-integrated specific
intensity, not the directional flux of an isotropic field.

See the :doc:`quickstart` for a practical introduction.


Documentation
-------------

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: Reference

   modules
   citation
