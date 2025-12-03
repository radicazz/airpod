from __future__ import annotations

from rich.console import Console
from rich.theme import Theme


# One Dark-inspired palette tuned for Rich output
PALETTE = {
    "fg": "#abb2bf",
    "fg_muted": "#5c6370",
    "bg": "#1e222a",
    "bg_alt": "#21252b",
    "bg_offset": "#2c323c",
    "green": "#98c379",
    "yellow": "#e5c07b",
    "orange": "#d19a66",
    "blue": "#61afef",
    "cyan": "#56b6c2",
    "purple": "#c678dd",
    "red": "#e06c75",
}

_theme = Theme(
    {
        "text": PALETTE["fg"],
        "muted": PALETTE["fg_muted"],
        "accent": PALETTE["orange"],
        "ok": PALETTE["green"],
        "warn": PALETTE["yellow"],
        "error": f"bold {PALETTE['red']}",
        "info": PALETTE["blue"],
        "alias": PALETTE["purple"],
        "section": f"bold {PALETTE['orange']}",
    }
)

console = Console(theme=_theme, style=PALETTE["fg"])


def status_spinner(message: str):
    """Return a Rich status spinner context manager."""
    return console.status(f"[info]{message}[/]")
