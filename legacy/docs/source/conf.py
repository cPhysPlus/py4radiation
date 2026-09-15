# Import libraries
import os
import sys

# Path for extensions
sys.path.insert(0, os.path.abspath('../..'))

project = 'py4radiation'
copyright = '2025, Yachay Tech University'
author = 'D. Villarruel, W. E. Banda-Barragan, B. Casavecchia'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx_rtd_theme',
]

templates_path = ['_templates']
exclude_patterns = ['_build']

# HTML for ReadTheDocs
html_theme = 'sphinx_rtd_theme'

# Add print statements to check the python path
print("Python Path:")
for path in sys.path:
    print(path)
