Installation
============

py4radiation requires Python 3.11 or newer.

The package can be installed from source using pip.
Cloudy is an external dependency required for executing
photoionisation calculations.


Installing py4radiation
-----------------------

Clone the repository and navigate to its root directory:

.. code-block:: bash

   git clone https://github.com/cPhysPlus/py4radiation.git
   cd py4radiation

Install the package:

.. code-block:: bash

   python -m pip install .


Development installation
------------------------

For development, an editable installation is recommended:

.. code-block:: bash

   python -m pip install -e .

With an editable installation, modifications to the Python
source code become available without reinstalling the package.


Python dependencies
-------------------

The principal Python dependencies are:

* NumPy for numerical calculations.
* Requests for downloading reference spectra.
* Platformdirs for managing cache directories.
* h5py for producing HDF5 ionisation tables.

These dependencies are installed automatically by pip.

MPI support is optional and requires mpi4py.


Installing Cloudy
-----------------

py4radiation uses Cloudy to calculate the radiative heating,
cooling and ionisation properties of astrophysical gas.

Cloudy is not distributed with py4radiation and must be
installed independently.

We recommend Cloudy version C13.05 for compatibility with
the current pyCIAO workflow.

The Cloudy executable must be available on the system.
Its location is supplied when generating the parameter files,
through the ``cloudy_path`` argument of
:class:`~py4radiation.radiation.parfiles.ParameterFiles`.

.. note::

   Cloudy is only required when executing photoionisation
   calculations. Existing Cloudy outputs can be processed
   without launching new calculations.


Optional MPI support
--------------------

pyCIAO supports both Python multiprocessing and MPI.

To install py4radiation with MPI support, run:

.. code-block:: bash

   python -m pip install ".[mpi]"

For an editable installation:

.. code-block:: bash

   python -m pip install -e ".[mpi]"

A compatible MPI implementation must also be installed
and configured on the system.

MPI support is particularly useful for distributing large
sets of Cloudy calculations across multiple computing nodes.

Without MPI, pyCIAO can still distribute calculations
using Python multiprocessing.


Offline environments
--------------------

py4radiation supports locally stored Starburst99 and HM2012
tables, making it suitable for air-gapped high-performance
computing (HPC) environments.

By default, the package retrieves and caches the required
reference spectra when they are first requested.

Alternatively, users can supply existing files through
the following arguments:

* ``sb99_path`` for Starburst99 tables.
* ``hm12_path`` for the Haardt & Madau (2012) UV background.

For example:

.. code-block:: python

   from py4radiation import SED

   sed = SED(
       run_name="offline_model",
       table_id="8b",
       sb99_path="/path/to/fig8b.dat",
       distance_kpc=1.0,
       age_myr=3,
   )

   sed.write_outfile()

No internet connection is required to load the reference
spectrum when the corresponding local file is provided.

.. note::

   Offline access to reference spectra is separate from
   offline installation of Python dependencies. On an
   air-gapped system, the required Python packages must
   also be installed from locally available distributions.


Building the documentation
--------------------------

The documentation is generated using Sphinx, Furo and Numpydoc.

From the repository root, install the documentation
dependencies:

.. code-block:: bash

   python -m pip install -r docs/requirements.txt

Build the HTML documentation:

.. code-block:: bash

   python -m sphinx -b html docs/source docs/_build/html

The generated documentation can be viewed by opening:

.. code-block:: text

   docs/_build/html/index.html
