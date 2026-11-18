import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

project = "py4radiation"
copyright = "2026, D. Villarruel-Yanez, W. E. Banda-Barragan, B. Casavecchia"
author = "D. Villarruel-Yanez, W. E. Banda-Barragan, B. Casavecchia"

with (ROOT / "pyproject.toml").open("rb") as f:
    release = tomllib.load(f)["project"]["version"]

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
html_theme = "furo"
html_title = "py4radiation"

autodoc_typehints = "description"
autodoc_typehints_format = "short"
autodoc_preserve_defaults = True
autodoc_typehints_description_target = "documented"
