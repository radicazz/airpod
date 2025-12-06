"""Tests for airpods.state module."""

from __future__ import annotations

from pathlib import Path

import pytest

from airpods import state


@pytest.fixture
def temp_state_root(tmp_path: Path):
    """Override state root to use temp directory for tests."""
    state.set_state_root(tmp_path)
    yield tmp_path
    state.clear_state_root_override()


def test_gateway_caddyfile_path(temp_state_root: Path):
    """Test gateway_caddyfile_path returns correct path."""
    expected = temp_state_root / "volumes" / "gateway" / "Caddyfile"
    assert state.gateway_caddyfile_path() == expected


def test_ensure_gateway_caddyfile_creates_file(temp_state_root: Path):
    """Test ensure_gateway_caddyfile creates file with content."""
    content = """
{
  auto_https off
  admin off
}

:80 {
  respond "Hello, world!"
}
""".strip()

    result_path = state.ensure_gateway_caddyfile(content)
    
    # Verify path is correct
    expected_path = temp_state_root / "volumes" / "gateway" / "Caddyfile"
    assert result_path == expected_path
    
    # Verify file was created
    assert result_path.exists()
    assert result_path.is_file()
    
    # Verify content matches
    written_content = result_path.read_text(encoding="utf-8")
    assert written_content == content


def test_ensure_gateway_caddyfile_creates_parent_dirs(temp_state_root: Path):
    """Test ensure_gateway_caddyfile creates parent directories."""
    gateway_dir = temp_state_root / "volumes" / "gateway"
    assert not gateway_dir.exists()
    
    state.ensure_gateway_caddyfile("test content")
    
    assert gateway_dir.exists()
    assert gateway_dir.is_dir()


def test_ensure_gateway_caddyfile_overwrites_existing(temp_state_root: Path):
    """Test ensure_gateway_caddyfile overwrites existing file."""
    initial_content = "initial"
    updated_content = "updated"
    
    # Create initial file
    path = state.ensure_gateway_caddyfile(initial_content)
    assert path.read_text(encoding="utf-8") == initial_content
    
    # Overwrite with new content
    path = state.ensure_gateway_caddyfile(updated_content)
    assert path.read_text(encoding="utf-8") == updated_content
