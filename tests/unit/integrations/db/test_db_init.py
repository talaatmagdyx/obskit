"""Tests for obskit.integrations.db.__init__ lazy import."""

from __future__ import annotations

import importlib

import pytest


class TestDbLazyImport:
    def test_lazy_import_instrument_sqlalchemy(self) -> None:
        import obskit.integrations.db as db_mod

        # Force fresh __getattr__ lookup
        if "instrument_sqlalchemy" in db_mod.__dict__:
            del db_mod.__dict__["instrument_sqlalchemy"]

        func = db_mod.instrument_sqlalchemy
        assert callable(func)

    def test_unknown_attr_raises(self) -> None:
        import obskit.integrations.db as db_mod

        with pytest.raises(AttributeError, match="no attribute"):
            _ = db_mod.nonexistent_thing  # type: ignore[attr-defined]
