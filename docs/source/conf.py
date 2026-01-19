# =============================================================================
# obskit Sphinx Documentation Configuration
# =============================================================================

import os
import sys
from datetime import datetime

# Add source to path for autodoc
sys.path.insert(0, os.path.abspath("../../src"))

# -- Project information -----------------------------------------------------

project = "obskit"
copyright = f"{datetime.now().year}, obskit Contributors"
author = "obskit Contributors"

# Version info - read directly from _version.py to avoid import issues
import re
_version_file = os.path.join(os.path.dirname(__file__), "../../src/obskit/_version.py")
try:
    with open(_version_file) as f:
        _version_content = f.read()
        _version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', _version_content)
        version = _version_match.group(1) if _version_match else "1.3.1"
        release = version
except (FileNotFoundError, AttributeError):
    version = "1.3.1"
    release = "1.3.1"

# -- General configuration ---------------------------------------------------

extensions = [
    # Core Sphinx extensions
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    # Third-party extensions
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
    "sphinxcontrib.mermaid",
    "myst_parser",
]

# Templates path
templates_path = ["_templates"]

# Source file extensions
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Main document
master_doc = "index"

# Exclude patterns
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Suppress warnings for docstring formatting issues
suppress_warnings = ["autodoc.import_cycle", "ref.python"]

# Don't fail on warnings
keep_warnings = False

# -- Options for HTML output -------------------------------------------------

# Use Furo theme
html_theme = "furo"

# Theme options
html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#2962FF",
        "color-brand-content": "#2962FF",
    },
    "dark_css_variables": {
        "color-brand-primary": "#82B1FF",
        "color-brand-content": "#82B1FF",
    },
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "top_of_page_button": "edit",
    "source_repository": "https://github.com/talaatmagdyx/obskit",
    "source_branch": "main",
    "source_directory": "docs/source/",
}

# Static files
html_static_path = ["_static"]

# Custom CSS
html_css_files = [
    "css/custom.css",
]

# Favicon and logo
# html_favicon = "_static/favicon.ico"
# html_logo = "_static/logo.svg"

# HTML title (use both version and release to satisfy CodeQL)
html_title = f"obskit {version} ({release})"

# -- Extension configuration -------------------------------------------------

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
    "show-inheritance": True,
}
autodoc_typehints = "both"
autodoc_typehints_format = "short"

# Autosummary settings
autosummary_generate = True

# Napoleon settings (Google/NumPy style docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_type_aliases = None
napoleon_custom_sections = [
    ("Example - Basic Usage", "examples"),
    ("Example - Database Operations", "examples"),
    ("Example - External API Calls", "examples"),
    ("Example - Background Monitoring", "examples"),
    ("Example - Integration with Message Queue", "examples"),
    ("Common Error Types by Resource", "notes"),
]
napoleon_preprocess_types = True

# Intersphinx mapping (requires network access)
# Set to empty dict for offline builds
intersphinx_mapping = {
    # "python": ("https://docs.python.org/3", None),
    # "prometheus_client": ("https://prometheus.github.io/client_python/", None),
    # "structlog": ("https://www.structlog.org/en/stable/", None),
    # "pydantic": ("https://docs.pydantic.dev/latest/", None),
}

# Timeout for intersphinx fetches (seconds)
intersphinx_timeout = 10

# Mermaid settings
mermaid_version = "10.6.1"
mermaid_init_js = """
mermaid.initialize({
    startOnLoad: true,
    theme: 'default',
    securityLevel: 'loose',
});
"""

# MyST parser settings
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "replacements",
    "smartquotes",
    "strikethrough",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 3

# Copy button settings
copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True

# TODO extension
todo_include_todos = True

