"""Open WebUI API client for programmatic plugin management."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests

from airpods.logging import console


def ensure_admin_user(base_url: str) -> tuple[str, str] | None:
    """Ensure an admin user exists and return credentials.

    Args:
        base_url: Base URL of Open WebUI instance

    Returns:
        Tuple of (email, password) if successful, None otherwise
    """
    email = "admin@airpods.local"
    password = "airpods-admin-default"

    try:
        # Try to sign up
        resp = requests.post(
            f"{base_url}/api/v1/auths/signup",
            json={"name": "Airpods Admin", "email": email, "password": password},
            timeout=10,
        )

        if resp.status_code in (200, 201):
            # User created successfully
            return (email, password)
        elif resp.status_code == 400:
            # Check if user already exists
            resp_data = resp.json() if resp.text else {}
            if "already" in str(resp_data).lower():
                return (email, password)
            else:
                console.print(f"[warn]Failed to create admin user: {resp_data}[/]")
                return None
        else:
            console.print(f"[warn]Failed to create admin user: {resp.status_code}[/]")
            return None

    except Exception as e:
        console.print(f"[error]Error creating admin user: {e}[/]")
        return None


def promote_user_to_admin(email: str) -> bool:
    """Promote a user to admin role via database update.

    Args:
        email: User email to promote

    Returns:
        True if successful, False otherwise
    """
    try:
        import subprocess

        # Update user role in database
        cmd = [
            "podman",
            "exec",
            "open-webui-0",
            "python3",
            "-c",
            f"import sqlite3; "
            f"conn = sqlite3.connect('/app/backend/data/webui.db'); "
            f"cursor = conn.cursor(); "
            f"cursor.execute(\"UPDATE user SET role='admin' WHERE email='{email}'\"); "
            f"conn.commit(); "
            f"print('Updated:', cursor.rowcount); "
            f"conn.close()",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and "Updated: 1" in result.stdout:
            return True
        else:
            console.print(f"[warn]Failed to promote user: {result.stderr}[/]")
            return False

    except Exception as e:
        console.print(f"[warn]Could not promote user to admin: {e}[/]")
        return False


def get_admin_token(base_url: str, email: str, password: str) -> str | None:
    """Get admin authentication token.

    Args:
        base_url: Base URL of Open WebUI instance
        email: Admin user email
        password: Admin user password

    Returns:
        Bearer token if successful, None otherwise
    """
    try:
        resp = requests.post(
            f"{base_url}/api/v1/auths/signin",
            json={"email": email, "password": password},
            timeout=10,
        )

        if resp.status_code == 200:
            data = resp.json()
            return data.get("token")
        else:
            console.print(f"[warn]Failed to login: {resp.status_code}[/]")
            return None

    except Exception as e:
        console.print(f"[error]Error getting admin token: {e}[/]")
        return None


def wait_for_webui(base_url: str, timeout: int = 60) -> bool:
    """Wait for Open WebUI to be ready.

    Args:
        base_url: Base URL of Open WebUI instance
        timeout: Maximum seconds to wait

    Returns:
        True if ready, False if timeout
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{base_url}/api/config", timeout=5)
            if resp.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(2)
    return False


def import_function_from_file(
    base_url: str, plugin_file: Path, admin_token: str
) -> dict[str, Any] | None:
    """Import a function/plugin into Open WebUI via API.

    Args:
        base_url: Base URL of Open WebUI instance
        plugin_file: Path to the plugin Python file
        admin_token: Admin user authentication token

    Returns:
        API response dict if successful, None otherwise
    """
    try:
        function_code = plugin_file.read_text(encoding="utf-8")
        function_id = plugin_file.stem

        headers = {"Authorization": f"Bearer {admin_token}"}

        payload = {
            "id": function_id,
            "name": function_id.replace("_", " ").title(),
            "type": "filter",
            "content": function_code,
            "meta": {
                "description": f"Auto-imported from {plugin_file.name}",
                "manifest": {},
            },
        }

        resp = requests.post(
            f"{base_url}/api/v1/functions/create",
            json=payload,
            headers=headers,
            timeout=10,
        )

        if resp.status_code in (200, 201):
            return resp.json()
        elif resp.status_code == 409:
            # Function already exists, skip silently
            return {"id": function_id, "status": "exists"}
        elif resp.status_code == 401:
            console.print(
                f"[warn]Authentication failed for {function_id} - admin user may not have permissions[/]"
            )
            return None
        else:
            console.print(
                f"[warn]Failed to import {function_id}: {resp.status_code} - {resp.text[:200]}[/]"
            )
        return None

    except Exception as e:
        console.print(f"[error]Error importing {plugin_file.name}: {e}[/]")
        return None


def auto_import_plugins(
    base_url: str, plugins_dir: Path, _webui_secret: str | None = None
) -> int:
    """Auto-import all plugins from directory into Open WebUI.

    Args:
        base_url: Base URL of Open WebUI instance
        plugins_dir: Directory containing plugin .py files
        _webui_secret: Deprecated, no longer used

    Returns:
        Number of plugins successfully imported
    """
    if not plugins_dir.exists():
        console.print(f"[warn]Plugins directory not found: {plugins_dir}[/]")
        return 0

    if not wait_for_webui(base_url, timeout=60):
        console.print("[error]Open WebUI did not become ready in time[/]")
        return 0

    # Ensure admin user exists and get credentials
    credentials = ensure_admin_user(base_url)
    if not credentials:
        console.print("[error]Failed to ensure admin user exists[/]")
        return 0

    email, password = credentials

    # Promote user to admin if needed (first user gets "pending" role by default)
    promote_user_to_admin(email)

    # Get authentication token
    admin_token = get_admin_token(base_url, email, password)
    if not admin_token:
        console.print("[error]Failed to get admin authentication token[/]")
        console.print(
            "[info]Plugins synced to filesystem. "
            "Create an admin account at the UI to enable auto-import.[/]"
        )
        return 0

    imported = 0
    plugin_files = [p for p in plugins_dir.glob("*.py") if p.name != "__init__.py"]

    for plugin_file in plugin_files:
        result = import_function_from_file(base_url, plugin_file, admin_token)
        if result:
            imported += 1

    return imported
