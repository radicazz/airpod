# Container outbound/`uv` install fix (2025-12-16)

## Symptoms
- Container startup got “stuck” when trying to install `uv`.
- From inside the `comfyui` container, DNS and plain HTTP worked, but **HTTPS requests would connect and complete the TLS handshake, then hang/time out**.

## What we found
- Host networking was OK (`curl https://example.com` on the host worked).
- You’re running **Mullvad WireGuard** (`wg0-mullvad`) with MTU **1380**.
- The container was on a Podman bridge network (`10.89.0.0/24`, `comfy_default`). With this setup, HTTPS was stalling (likely PMTU/MSS issues on forwarded traffic through the VPN).
- Separate issue observed in this environment: in the *docker-compat* path (docker CLI pointing at Podman), some containers ended up with **`/sys/fs/cgroup/pids.max=1`**, which makes shells fail with `can't fork: Resource temporarily unavailable` and breaks installers.

## Changes applied
### 1) `compose.yaml`: use host networking
File: `compose.yaml`
- Added:
  ```yaml
  network_mode: host
  ```
- Removed the published port mapping:
  ```yaml
  ports:
    - "8188:8188"
  ```

**Effect:** the container no longer uses the bridge network; it shares the host network stack.
- ComfyUI listens on **host port 8188 directly**.
- Outbound HTTPS from the container works (confirmed with `curl -I https://pypi.org/simple/`).

**Tradeoffs:**
- Less network isolation (container can bind to host interfaces).
- `ports:` cannot be used with `network_mode: host`.
- Port collisions are possible if something else uses `8188`.

### 2) `compose.yaml`: set a PID limit explicitly
File: `compose.yaml`
- Added:
  ```yaml
  pids_limit: 2048
  ```

**Effect:** avoids pathological “PIDs max = 1” / fork failures in some Podman+docker-compat situations.

### 3) Host firewall: TCP MSS clamping over Mullvad
You successfully added these rules (shown by `iptables -t mangle -S | grep TCPMSS`):
```bash
sudo iptables -t mangle -A FORWARD -o wg0-mullvad -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
sudo iptables -t mangle -A OUTPUT  -o wg0-mullvad -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
```

**Effect:** clamps TCP MSS to avoid PMTU blackholes (common when tunneling/bridging through VPNs with smaller MTUs).

Note: with `network_mode: host`, the container doesn’t rely on bridge forwarding, so the MSS rule may be less critical for this specific compose setup, but it can still help other bridged containers.

## How to recreate the fixes
### A) Re-apply compose changes
From this folder:
```bash
docker compose up -d --force-recreate
```

Verify:
```bash
docker exec comfyui sh -lc 'curl -4 -I --max-time 10 https://pypi.org/simple/ | head'
```

### B) Re-apply MSS clamp rules (idempotent)
```bash
sudo sh -lc 'iptables -t mangle -C FORWARD -o wg0-mullvad -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu 2>/dev/null || iptables -t mangle -A FORWARD -o wg0-mullvad -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu'
sudo sh -lc 'iptables -t mangle -C OUTPUT  -o wg0-mullvad -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu 2>/dev/null || iptables -t mangle -A OUTPUT  -o wg0-mullvad -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu'

sudo iptables -t mangle -S | grep TCPMSS
```

## How to rollback
### Roll back host networking
Edit `compose.yaml`:
- Remove `network_mode: host`
- Restore the `ports:` section:
  ```yaml
  ports:
    - "8188:8188"
  ```
Then:
```bash
docker compose up -d --force-recreate
```

### Remove MSS clamp rules
```bash
sudo iptables -t mangle -D FORWARD -o wg0-mullvad -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
sudo iptables -t mangle -D OUTPUT  -o wg0-mullvad -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
```
