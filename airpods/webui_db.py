"""Direct database operations for Open WebUI function management."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from airpods.logging import console


def import_functions_via_db(plugins_dir: Path, admin_user_id: str = "system") -> int:
    """Import functions directly into the database via SQL.

    This bypasses the API entirely and inserts functions directly into
    the SQLite database using podman exec.

    Args:
        plugins_dir: Directory containing plugin .py files
        admin_user_id: User ID to assign as owner (default: "system")

    Returns:
        Number of functions successfully imported
    """
    if not plugins_dir.exists():
        console.print(f"[warn]Plugins directory not found: {plugins_dir}[/]")
        return 0

    imported = 0
    plugin_files = [p for p in plugins_dir.glob("*.py") if p.name != "__init__.py"]
    timestamp = int(time.time())

    for plugin_file in plugin_files:
        try:
            function_id = plugin_file.stem
            content = plugin_file.read_text(encoding="utf-8")

            # Escape single quotes for SQL
            content_escaped = content.replace("'", "''")

            # Create meta JSON
            meta = {
                "description": f"Auto-imported from {plugin_file.name}",
                "manifest": {},
            }
            meta_json = json.dumps(meta).replace("'", "''")

            # Build SQL INSERT with ON CONFLICT (upsert)
            sql = f"""
            INSERT INTO function (
                id, user_id, name, type, content, meta,
                created_at, updated_at, is_active, is_global
            ) VALUES (
                '{function_id}',
                '{admin_user_id}',
                '{function_id.replace("_", " ").title()}',
                'filter',
                '{content_escaped}',
                '{meta_json}',
                {timestamp},
                {timestamp},
                1,
                0
            )
            ON CONFLICT(id) DO UPDATE SET
                content = excluded.content,
                updated_at = excluded.updated_at;
            """

            # Execute via podman exec
            cmd = [
                "podman",
                "exec",
                "open-webui-0",
                "python3",
                "-c",
                f"import sqlite3; "
                f"conn = sqlite3.connect('/app/backend/data/webui.db'); "
                f"cursor = conn.cursor(); "
                f"cursor.execute({repr(sql)}); "
                f"conn.commit(); "
                f"print('Imported {function_id}:', cursor.rowcount); "
                f"conn.close()",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0 and "Imported" in result.stdout:
                imported += 1
            else:
                console.print(
                    f"[warn]Failed to import {function_id}: {result.stderr}[/]"
                )

        except Exception as e:
            console.print(f"[error]Error importing {plugin_file.name}: {e}[/]")

    return imported
