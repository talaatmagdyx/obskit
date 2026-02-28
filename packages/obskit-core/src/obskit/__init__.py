"""obskit — production-ready observability toolkit for Python microservices.

This __init__.py lives in obskit-core and serves two purposes:
1. Provides pkgutil-style namespace merging so all obskit-* sub-packages
   contribute to the single ``obskit`` namespace.
2. Re-exports the version so ``from obskit import __version__`` works.
"""
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)  # type: ignore[assignment]

from obskit._version import __version__, __version_info__

__all__ = ["__version__", "__version_info__"]
