from __future__ import annotations

from types import SimpleNamespace

import airpods.cli.help as cli_help


def test_command_description_falls_back_to_docstring():
    """Ensure help descriptions derive from docstrings when explicit help is missing."""

    def sample():
        """Docstring first line.

        Additional detail ignored."""

    command = SimpleNamespace(help=None, short_help=None, callback=sample)
    assert cli_help._command_description(command) == "Docstring first line."
