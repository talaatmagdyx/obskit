"""
Version Information
===================

This module contains version information for the obskit package.

The version follows Semantic Versioning (https://semver.org/):
- MAJOR version for incompatible API changes
- MINOR version for new functionality in a backwards compatible manner
- PATCH version for backwards compatible bug fixes

Stability Commitment
--------------------
As of v1.0.0, all public APIs are considered stable. We commit to:
- No breaking changes within a major version
- Minimum 2 minor versions deprecation notice
- Clear migration guides for major version upgrades

Usage
-----
>>> from obskit import __version__, __version_info__
>>> print(__version__)  # "1.0.0"
>>> print(__version_info__)  # (1, 0, 0)
"""

# Version string
__version__: str = "1.0.0"

# Version tuple for programmatic comparison
__version_info__: tuple[int, int, int] = (1, 0, 0)
