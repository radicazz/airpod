from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def detect_dns_servers() -> List[str]:
    """Return DNS servers that containers can use.

    Prefers non-loopback nameservers from resolv.conf. If the system uses
    a local stub resolver (e.g., systemd-resolved at 127.0.0.53), attempts
    to read a non-stub resolv.conf before falling back to public DNS.
    """
    import ipaddress
    from pathlib import Path

    def _from_resolv(path: Path) -> List[str]:
        servers: list[str] = []
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return servers
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if not line.startswith("nameserver "):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            candidate = parts[1].strip()
            try:
                ip = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if ip.is_loopback:
                continue
            if candidate not in servers:
                servers.append(candidate)
        return servers

    primary = Path("/etc/resolv.conf")
    servers = _from_resolv(primary)
    if servers:
        return servers

    # Common non-stub resolv.conf locations on Linux.
    for candidate in (
        Path("/run/systemd/resolve/resolv.conf"),
        Path("/run/NetworkManager/no-stub-resolv.conf"),
    ):
        servers = _from_resolv(candidate)
        if servers:
            return servers

    # Last resort: public resolvers. Users on restricted networks should
    # override runtime.network.dns_servers in config.toml.
    return ["1.1.1.1", "8.8.8.8"]


def _run_command(args: List[str]) -> Tuple[bool, str]:
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        output = exc.output if isinstance(exc, subprocess.CalledProcessError) else ""
        return False, (output or str(exc))
    return True, proc.stdout.strip()


def check_dependency(
    name: str, version_args: Optional[List[str]] = None
) -> CheckResult:
    if shutil.which(name) is None:
        return CheckResult(name=name, ok=False, detail="not found in PATH")
    if version_args:
        ok, output = _run_command([name] + version_args)
        return CheckResult(name=name, ok=ok, detail=output if ok else "unable to run")
    return CheckResult(name=name, ok=True, detail="available")


def detect_gpu() -> Tuple[bool, str]:
    """Detect NVIDIA GPU via nvidia-smi; fail softly."""
    if shutil.which("nvidia-smi") is None:
        return False, "nvidia-smi not found"
    ok, output = _run_command(
        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"]
    )
    if not ok:
        return False, "nvidia-smi failed"
    gpu_names = [line.strip() for line in output.splitlines() if line.strip()]
    if not gpu_names:
        return False, "no GPUs detected"
    return True, ", ".join(gpu_names)


def detect_cuda_compute_capability() -> Tuple[bool, str, Optional[Tuple[int, int]]]:
    """Detect NVIDIA GPU compute capability via nvidia-smi; fail softly.

    Returns:
        (has_gpu, gpu_name, compute_capability)

        has_gpu: True if GPU detected and query succeeded
        gpu_name: Name of the first GPU, or error message if failed
        compute_capability: (major, minor) tuple like (7, 5) for compute 7.5, or None if failed
    """
    if shutil.which("nvidia-smi") is None:
        return False, "nvidia-smi not found", None

    # Query both name and compute capability
    ok, output = _run_command(
        ["nvidia-smi", "--query-gpu=name,compute_cap", "--format=csv,noheader,nounits"]
    )
    if not ok:
        return False, "nvidia-smi failed", None

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return False, "no GPUs detected", None

    # Parse first GPU line: "NVIDIA GeForce GTX 1650, 7.5"
    try:
        gpu_name, compute_cap_str = lines[0].split(", ", 1)
        gpu_name = gpu_name.strip()
        compute_cap_str = compute_cap_str.strip()

        # Parse compute capability like "7.5" into (7, 5)
        major_str, minor_str = compute_cap_str.split(".", 1)
        major = int(major_str)
        minor = int(minor_str)

        return True, gpu_name, (major, minor)
    except (ValueError, IndexError) as exc:
        # Fallback to just GPU name if compute capability parsing fails
        gpu_name = lines[0].split(",")[0].strip() if "," in lines[0] else lines[0]
        return False, f"{gpu_name} (compute capability parse failed: {exc})", None


def detect_vpn_mtu_issues() -> Tuple[bool, Optional[str], Optional[int], bool]:
    """Detect VPN interfaces with low MTU and check for MSS clamping.

    Returns:
        (has_vpn_issue, vpn_interface, mtu, has_mss_clamping)

        has_vpn_issue: True if a VPN interface with MTU < 1500 is detected
        vpn_interface: Name of the first VPN interface found, or None
        mtu: MTU value of the VPN interface, or None
        has_mss_clamping: True if TCP MSS clamping rules are configured
    """
    from pathlib import Path

    # Common VPN interface patterns
    vpn_patterns = ["wg", "tun", "ppp", "vpn", "mullvad", "proton"]

    # Scan network interfaces for VPN with low MTU
    vpn_interface = None
    vpn_mtu = None

    try:
        net_dir = Path("/sys/class/net")
        if not net_dir.exists():
            return False, None, None, False

        for iface_dir in net_dir.iterdir():
            if not iface_dir.is_dir():
                continue

            iface_name = iface_dir.name
            # Skip loopback and common non-VPN interfaces
            if iface_name in ("lo", "docker0", "podman0"):
                continue

            # Read MTU
            mtu_file = iface_dir / "mtu"
            if not mtu_file.exists():
                continue

            try:
                mtu = int(mtu_file.read_text().strip())
            except (ValueError, OSError):
                continue

            # Check if this looks like a VPN interface with low MTU
            is_vpn_pattern = any(
                pattern in iface_name.lower() for pattern in vpn_patterns
            )
            if is_vpn_pattern and mtu < 1500:
                vpn_interface = iface_name
                vpn_mtu = mtu
                break

    except OSError:
        # Can't read /sys/class/net, assume no VPN issue
        return False, None, None, False

    if not vpn_interface:
        return False, None, None, False

    # Check for existing MSS clamping rules
    has_mss_clamping = False
    try:
        result = subprocess.run(
            ["iptables", "-t", "mangle", "-S"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            output = result.stdout
            # Look for TCPMSS rules targeting our VPN interface
            for line in output.splitlines():
                if "TCPMSS" in line and vpn_interface in line:
                    has_mss_clamping = True
                    break
    except (FileNotFoundError, PermissionError):
        # iptables not available or no permission, assume no clamping
        pass

    return True, vpn_interface, vpn_mtu, has_mss_clamping
