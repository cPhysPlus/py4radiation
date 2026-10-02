import os
import sys

sys.path.insert(0, os.path.abspath("../../src"))

project = "py4radiation"
copyright = "2026, D. Villarruel-Yanez, W. E. Banda-Barragan, B. Casavecchia"
author = "D. Villarruel-Yanez, W. E. Banda-Barragan, B. Casavecchia"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "numpydoc",
]

templates_path = ["_templates"]
exclude_patterns = []

html_static_path = ["_static"]
html_css_files = ["custom.css"]

autosummary_generate = True
numpydoc_show_class_members = False
html_theme = "sphinx_rtd_theme"

autodoc_typehints = "description"
autodoc_typehints_format = "short"
autodoc_preserve_defaults = True
autodoc_typehints_description_target = "documented"
