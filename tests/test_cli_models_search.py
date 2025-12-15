"""Tests for the models search command."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from airpods.cli import app

runner = CliRunner()


@pytest.fixture
def mock_ollama_search():
    """Mock Ollama library search results."""
    return [
        {
            "name": "llama3.2",
            "description": "Meta's Llama 3.2 model",
            "tags": ["llama", "meta", "instruct"],
            "size": "small",
        },
        {
            "name": "llama3.1:8b",
            "description": "Meta's Llama 3.1 8B model",
            "tags": ["llama", "meta", "instruct"],
            "size": "medium",
        },
    ]


@pytest.fixture
def mock_hf_search():
    """Mock HuggingFace search results."""
    return [
        {
            "repo_id": "bartowski/Llama-3.2-3B-Instruct-GGUF",
            "author": "bartowski",
            "model_name": "Llama-3.2-3B-Instruct-GGUF",
            "downloads": 125000,
            "likes": 42,
        },
        {
            "repo_id": "hugging-quants/Llama-3.2-1B-Instruct-GGUF",
            "author": "hugging-quants",
            "model_name": "Llama-3.2-1B-Instruct-GGUF",
            "downloads": 80000,
            "likes": 28,
        },
    ]


def test_models_search_both_sources(mock_ollama_search, mock_hf_search):
    """Test searching both Ollama and HuggingFace."""
    with (
        patch("airpods.ollama.search_ollama_library") as mock_ol,
        patch("airpods.ollama.search_huggingface_models") as mock_hf,
    ):
        mock_ol.return_value = mock_ollama_search
        mock_hf.return_value = mock_hf_search

        result = runner.invoke(app, ["models", "search", "llama"])

        assert result.exit_code == 0
        assert "Searching for llama" in result.stdout
        assert "Ollama Library:" in result.stdout
        assert "HuggingFace (GGUF):" in result.stdout
        assert "llama3.2" in result.stdout
        assert "bartowski/Llama-3.2-3B-Instruct-GGUF" in result.stdout


def test_models_search_ollama_only(mock_ollama_search):
    """Test searching only Ollama library."""
    with patch("airpods.ollama.search_ollama_library") as mock_ol:
        mock_ol.return_value = mock_ollama_search

        result = runner.invoke(app, ["models", "search", "--source", "ollama", "llama"])

        assert result.exit_code == 0
        assert "Ollama Library:" in result.stdout
        assert "HuggingFace (GGUF):" not in result.stdout


def test_models_search_huggingface_only(mock_hf_search):
    """Test searching only HuggingFace."""
    with patch("airpods.ollama.search_huggingface_models") as mock_hf:
        mock_hf.return_value = mock_hf_search

        result = runner.invoke(
            app, ["models", "search", "--source", "huggingface", "llama"]
        )

        assert result.exit_code == 0
        assert "HuggingFace (GGUF):" in result.stdout
        assert "Ollama Library:" not in result.stdout


def test_models_search_with_limit(mock_ollama_search):
    """Test search with custom limit."""
    with patch("airpods.ollama.search_ollama_library") as mock_ol:
        mock_ol.return_value = mock_ollama_search

        result = runner.invoke(
            app, ["models", "search", "--limit", "10", "--source", "ollama", "llama"]
        )

        assert result.exit_code == 0
        # Verify the limit was passed
        mock_ol.assert_called_once_with("llama", 10)


def test_models_search_invalid_source():
    """Test search with invalid source."""
    result = runner.invoke(app, ["models", "search", "--source", "invalid", "llama"])

    assert result.exit_code == 1
    assert "Invalid source" in result.stdout


def test_models_search_no_results():
    """Test search with no results."""
    with (
        patch("airpods.ollama.search_ollama_library") as mock_ol,
        patch("airpods.ollama.search_huggingface_models") as mock_hf,
    ):
        mock_ol.return_value = []
        mock_hf.return_value = []

        result = runner.invoke(app, ["models", "search", "nonexistent"])

        assert result.exit_code == 0
        assert "No results from Ollama library" in result.stdout
        assert "No results from HuggingFace" in result.stdout


def test_models_search_hf_alias():
    """Test that 'hf' works as alias for 'huggingface'."""
    with patch("airpods.ollama.search_huggingface_models") as mock_hf:
        mock_hf.return_value = []

        result = runner.invoke(app, ["models", "search", "--source", "hf", "llama"])

        assert result.exit_code == 0
        assert "HuggingFace" in result.stdout
        assert "Ollama Library:" not in result.stdout
