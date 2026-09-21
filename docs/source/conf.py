import os
import sys

sys.path.insert(0, os.path.abspath('../../src'))

project = 'py4radiation'
copyright = '2026, D. Villarruel-Yanez, W. E. Banda-Barragan, B. Casavecchia'
author = 'D. Villarruel-Yanez, W. E. Banda-Barragan, B. Casavecchia'
release = '0.1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon'
]

templates_path = ['_templates']
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
