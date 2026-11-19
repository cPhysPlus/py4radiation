Testing
=======

py4radiation includes a compact pytest suite that verifies
the main numerical operations and interfaces.

The tests use small synthetic datasets with independently
known expected results. They are designed to run without
Cloudy or internet access.


Running the tests
-----------------

From the repository root, install py4radiation in editable
mode:

.. code-block:: bash

   python -m pip install -e .

Install pytest:

.. code-block:: bash

   python -m pip install pytest

Run the test suite:

.. code-block:: bash

   python -m pytest tests/ -v


Test coverage
-------------

The test suite focuses on five components.


Spectral preparation
~~~~~~~~~~~~~~~~~~~~

``test_sed.py`` verifies spectral conversions, stellar
population scaling, distance dilution and the HM2012
intensity convention.


Cloudy input preparation
~~~~~~~~~~~~~~~~~~~~~~~~

``test_cloudy_inputs.py`` checks the consistency of
Cloudy continuum files, parameter grids, generated
execution tasks and master run records.


Heating and cooling tables
~~~~~~~~~~~~~~~~~~~~~~~~~~

``test_hc_tables.py`` verifies the association between
physical coordinates and heating/cooling quantities,
including temperature-grid consistency.


Ionisation tables
~~~~~~~~~~~~~~~~~

``test_ib_tables.py`` verifies the HDF5 dimensions,
axis ordering, coordinate metadata and duplicated
redshift dimension.


Execution and failure handling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``test_runner.py`` checks the reporting of successful,
partially failed and failed calculations.

Cloudy subprocesses are simulated to keep the tests
independent of an external Cloudy installation.


Scope
-----

These tests validate the numerical operations and data
structures implemented by py4radiation.

They do not independently validate the astrophysical
predictions of Starburst99, HM2012 or Cloudy.

The executed notebooks and their reference data provide
additional examples for users wishing to compare the
results of complete scientific workflows.
