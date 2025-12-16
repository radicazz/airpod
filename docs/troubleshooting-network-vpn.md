# docs/troubleshooting-network-vpn

This guide helps diagnose and fix container networking issues when running airpods on systems with VPNs or non-standard network configurations.

## Symptoms

- Container startup hangs when downloading packages (e.g., installing `uv` in ComfyUI)
- DNS lookups work but HTTPS connections stall after TLS handshake
- `curl http://example.com` works inside containers but `curl https://example.com` times out
- Containers can't pull Python packages from PyPI or install dependencies

## Common Causes

### 1. VPN MTU/PMTU Issues

**Problem**: VPNs like WireGuard often use smaller MTU sizes (e.g., 1380 instead of the standard 1500). When containers use bridge networking, TCP packets may exceed the Path MTU, causing fragmentation issues or blackhole scenarios where large packets are silently dropped.

**Diagnosis**:
```bash
# Check your VPN interface MTU
ip link show wg0-mullvad  # or your VPN interface name
# Look for "mtu 1380" or similar

# Test from inside a running container
airpods start comfyui
podman exec comfyui-0 sh -c 'curl -I --max-time 10 https://pypi.org/simple/'
# If this times out but HTTP works, you likely have an MTU issue
```

**Solution 1: TCP MSS Clamping** (System-wide, requires root):

Use the included `mss-clamping` script to automatically configure MSS clamping:

```bash
# Check for VPN MTU issues
scripts/mss-clamping check

# Enable MSS clamping (auto-detects VPN interface)
sudo scripts/mss-clamping enable

# Or specify interface manually
sudo scripts/mss-clamping enable wg0-mullvad

# Check status
scripts/mss-clamping status

# Disable if needed
sudo scripts/mss-clamping disable
```

**Manual iptables rules** (if you prefer manual configuration):

```bash
# Replace wg0-mullvad with your VPN interface name
VPN_IFACE="wg0-mullvad"

# FORWARD chain: for traffic forwarded through the VPN (bridged containers)
sudo iptables -t mangle -A FORWARD -o "$VPN_IFACE" -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu

# OUTPUT chain: for traffic originating from the host (host-network containers)
sudo iptables -t mangle -A OUTPUT -o "$VPN_IFACE" -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu

# Verify rules are active
sudo iptables -t mangle -S | grep TCPMSS
```

To make these rules persistent across reboots, use your distribution's firewall management tool (e.g., `iptables-persistent`, `firewalld`, or `nftables`).

**Solution 2: Host Networking** (Per-service, no root required):

Configure specific services to use host networking instead of pod/bridge networking. This bypasses the bridge entirely and uses the host's network stack directly.

Edit your `config.toml`:

```toml
[services.comfyui]
network_mode = "host"  # Use host networking instead of pod
# Remove or comment out network_aliases when using host mode
# network_aliases = ["comfyui"]
```

**Tradeoffs of Host Networking**:
- ✅ Bypasses MTU/bridge issues completely
- ✅ No NAT overhead, slightly better performance
- ❌ Less network isolation (container can bind to any host interface)
- ❌ Service-to-service communication via network aliases won't work (must use `localhost` or host IP)
- ❌ Port conflicts possible if multiple processes try to bind the same port

### 2. PID Limit Issues (docker-compat mode)

**Problem**: In some Podman configurations (especially when using docker-compose compatibility), containers may inherit a pathologically low PID limit (`pids.max=1`), causing fork failures.

**Symptoms**:
```
sh: can't fork: Resource temporarily unavailable
```

**Solution**: airpods now sets a safe default PID limit of 2048 for all containers. You can customize this per-service in `config.toml`:

```toml
[services.comfyui]
pids_limit = 4096  # Increase if you see fork errors
```

### 3. DNS Resolution Failures

**Problem**: Containers can't resolve domain names.

**Diagnosis**:
```bash
podman exec comfyui-0 nslookup google.com
# If this fails, DNS is not working
```

**Solution**: Ensure DNS servers are configured in `config.toml`:

```toml
[runtime.network]
dns_servers = ["8.8.8.8", "1.1.1.1"]  # Google DNS and Cloudflare DNS
```

If using a custom VPN DNS, add your VPN's DNS servers instead.

## Configuration Reference

### Per-Service Network Mode

```toml
[services.ollama]
network_mode = "pod"  # Default: use pod/bridge networking (supports network aliases)

[services.comfyui]
network_mode = "host"  # Use host networking (bypasses bridge, no aliases)
```

### Per-Service PID Limits

```toml
[services.comfyui]
pids_limit = 2048  # Default: safe limit for most workloads
```

### Network-wide Settings

```toml
[runtime.network]
driver = "bridge"
subnet = "10.89.0.0/16"
dns_servers = ["8.8.8.8", "1.1.1.1"]
```

## Recommended Approach

1. **Start with MSS clamping** if you're on a VPN: this fixes the issue system-wide without changing service isolation.
2. **Use host networking** for specific services if MSS clamping isn't an option or doesn't fully resolve the issue.
3. **Keep Ollama and Open WebUI on pod networking** so they can communicate via network aliases (`http://ollama:11434`).

## Example: Mixed Configuration

```toml
# config.toml - ComfyUI on host network, Ollama/WebUI on bridge

[runtime.network]
dns_servers = ["8.8.8.8", "1.1.1.1"]

[services.ollama]
network_mode = "pod"  # Keep on bridge for inter-service communication
network_aliases = ["ollama"]

[services.open-webui]
network_mode = "pod"  # Can reach Ollama via http://ollama:11434
network_aliases = ["webui", "open-webui"]
env.OLLAMA_BASE_URL = "http://ollama:11434"

[services.comfyui]
network_mode = "host"  # Bypass bridge for VPN compatibility
# No network_aliases needed in host mode
# Access via http://localhost:8188 from host
```

## Further Reading

- [Podman networking documentation](https://docs.podman.io/en/latest/markdown/podman-network.1.html)
- [TCP MSS/MTU issues with VPNs](https://www.kernel.org/doc/Documentation/networking/ip-sysctl.txt)
- [Understanding Path MTU Discovery](https://packetlife.net/blog/2008/aug/18/path-mtu-discovery/)
