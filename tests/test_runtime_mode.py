"""Tests for runtime mode detection."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from airpods.runtime_mode import get_mode_name, get_resource_prefix, is_dev_mode


class TestRuntimeMode:
    """Test runtime mode detection and utilities."""

    def setup_method(self):
        """Clear the lru_cache before each test."""
        is_dev_mode.cache_clear()

    def test_production_mode_default(self):
        """By default (no git repo), should be in production mode."""
        with patch.dict(os.environ, {}, clear=True):
            # Mock detect_repo_root to return None (no git repo found)
            with patch("airpods.runtime_mode.detect_repo_root", return_value=None):
                is_dev_mode.cache_clear()
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

    def test_prod_mode_via_env_var(self):
        """AIRPODS_DEV_MODE=0 should force production mode."""
        # Even when in a git repo, AIRPODS_DEV_MODE=0 forces production
        with patch.dict(os.environ, {"AIRPODS_DEV_MODE": "0"}):
            with patch(
                "airpods.runtime_mode.detect_repo_root", return_value=Path("/repo")
            ):
                is_dev_mode.cache_clear()
                assert is_dev_mode() is False
                assert get_resource_prefix() == "airpods"
                assert get_mode_name() == "production"

    def test_dev_mode_via_git_detection(self):
        """When package is in a git repo, should enable dev mode."""
        with patch.dict(os.environ, {}, clear=True):
            # Mock detect_repo_root to return a repo path
            with patch(
                "airpods.runtime_mode.detect_repo_root",
                return_value=Path("/home/user/airpods"),
            ):
                is_dev_mode.cache_clear()
                assert is_dev_mode() is True
                assert get_resource_prefix() == "airpods-dev"
                assert get_mode_name() == "development"

    def test_env_var_not_1(self):
        """AIRPODS_DEV_MODE set to '0' should force production mode."""
        with patch.dict(os.environ, {"AIRPODS_DEV_MODE": "0"}):
            with patch("airpods.runtime_mode.detect_repo_root", return_value=None):
                is_dev_mode.cache_clear()
                assert is_dev_mode() is False
                assert get_resource_prefix() == "airpods"

    def test_env_var_invalid_value(self):
        """AIRPODS_DEV_MODE set to anything other than '0' or '1' should fall back to git detection."""
        # Invalid value -> falls back to git detection
        with patch.dict(os.environ, {"AIRPODS_DEV_MODE": "true"}):
            with patch("airpods.runtime_mode.detect_repo_root", return_value=None):
                is_dev_mode.cache_clear()
                assert is_dev_mode() is False

    def test_env_var_takes_precedence(self):
        """Env var should take precedence over git detection."""
        # Force dev mode via env var, even when no git repo
        with patch.dict(os.environ, {"AIRPODS_DEV_MODE": "1"}):
            with patch("airpods.runtime_mode.detect_repo_root", return_value=None):
                is_dev_mode.cache_clear()
                assert is_dev_mode() is True

        # Force production mode via env var, even when in git repo
        with patch.dict(os.environ, {"AIRPODS_DEV_MODE": "0"}):
            with patch(
                "airpods.runtime_mode.detect_repo_root", return_value=Path("/repo")
            ):
                is_dev_mode.cache_clear()
                assert is_dev_mode() is False

    def test_caching(self):
        """Mode detection should be cached."""
        with patch.dict(os.environ, {"AIRPODS_DEV_MODE": "1"}):
            is_dev_mode.cache_clear()
            assert is_dev_mode() is True

            # Change env var, but should still return cached value
            os.environ.pop("AIRPODS_DEV_MODE")
            assert is_dev_mode() is True  # Still cached

            # Clear cache and check again - now falls back to git detection
            with patch("airpods.runtime_mode.detect_repo_root", return_value=None):
                is_dev_mode.cache_clear()
                assert is_dev_mode() is False  # Now reflects new state
