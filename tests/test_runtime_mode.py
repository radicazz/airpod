"""Tests for runtime mode detection."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

from airpods.runtime_mode import get_mode_name, get_resource_prefix, is_dev_mode


class TestRuntimeMode:
    """Test runtime mode detection and utilities."""

    def setup_method(self):
        """Clear the lru_cache before each test."""
        is_dev_mode.cache_clear()

    def test_production_mode_default(self):
        """By default, should be in production mode."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(sys, "argv", ["airpods"]):
                assert is_dev_mode() is False
                assert get_resource_prefix() == "airpods"
                assert get_mode_name() == "production"

    def test_dev_mode_via_env_var(self):
        """AIRPODS_DEV_MODE=1 should enable dev mode."""
        with patch.dict(os.environ, {"AIRPODS_DEV_MODE": "1"}):
            is_dev_mode.cache_clear()
            assert is_dev_mode() is True
            assert get_resource_prefix() == "airpods-dev"
            assert get_mode_name() == "development"

    def test_dev_mode_via_script_name(self):
        """dairpods in script name should enable dev mode."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(sys, "argv", ["dairpods"]):
                is_dev_mode.cache_clear()
                assert is_dev_mode() is True
                assert get_resource_prefix() == "airpods-dev"
                assert get_mode_name() == "development"

    def test_dev_mode_via_script_path(self):
        """/some/path/dairpods should enable dev mode."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(sys, "argv", ["/usr/local/bin/dairpods"]):
                is_dev_mode.cache_clear()
                assert is_dev_mode() is True
                assert get_resource_prefix() == "airpods-dev"
                assert get_mode_name() == "development"

    def test_env_var_not_1(self):
        """AIRPODS_DEV_MODE set to anything other than '1' should be production."""
        with patch.dict(os.environ, {"AIRPODS_DEV_MODE": "0"}):
            is_dev_mode.cache_clear()
            assert is_dev_mode() is False
            assert get_resource_prefix() == "airpods"

        with patch.dict(os.environ, {"AIRPODS_DEV_MODE": "true"}):
            is_dev_mode.cache_clear()
            assert is_dev_mode() is False

    def test_env_var_takes_precedence(self):
        """Env var should take precedence over script name."""
        with patch.dict(os.environ, {"AIRPODS_DEV_MODE": "1"}):
            with patch.object(sys, "argv", ["airpods"]):  # Production script name
                is_dev_mode.cache_clear()
                assert is_dev_mode() is True  # But env var forces dev mode

    def test_caching(self):
        """Mode detection should be cached."""
        with patch.dict(os.environ, {"AIRPODS_DEV_MODE": "1"}):
            is_dev_mode.cache_clear()
            assert is_dev_mode() is True

            # Change env var, but should still return cached value
            os.environ.pop("AIRPODS_DEV_MODE")
            assert is_dev_mode() is True  # Still cached

            # Clear cache and check again
            is_dev_mode.cache_clear()
            assert is_dev_mode() is False  # Now reflects new state
