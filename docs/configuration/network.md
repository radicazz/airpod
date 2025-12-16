# docs/configuration/network

This guide explains how to customize container networking for airpods using the `runtime.network` section and per-service `network_aliases`.

## Network Options

The `[runtime.network]` table controls how the shared pod network is created:

```toml
[runtime.network]
driver = "bridge"
subnet = "10.89.0.0/16"                  # optional custom subnet
gateway = "10.89.0.1"                    # optional custom gateway
dns_servers = ["8.8.8.8", "1.1.1.1"]     # DNS servers (required for external connectivity)
ipv6 = false
internal = false
```

- `driver`: Network driver (default: `"bridge"`).
- `subnet`: Custom subnet in CIDR format (for example, `"10.89.0.0/16"`).
- `gateway`: Custom gateway IP on the chosen subnet.
- `dns_servers`: List of DNS servers used by containers on this network. **Important**: Without DNS servers configured, containers cannot resolve external domain names and will have timeout issues when downloading models, images, or accessing external APIs. Default: `["8.8.8.8", "1.1.1.1"]` (Google DNS and Cloudflare DNS).
- `ipv6`: Enable IPv6 networking for the pod network.
- `internal`: Restrict external network access for increased isolation.

These settings apply to all services managed by airpods because they share the same network.

### Recreating the Network

If you've updated DNS settings or other network configuration, you'll need to recreate the network for the changes to take effect:

```bash
# Stop all services
airpods stop

# Remove the network (this is safe - volumes and data are preserved)
airpods clean --network

# Start services again - the network will be recreated with new settings
airpods start
```

## Service Network Aliases

Each service can define one or more `network_aliases` to simplify inter-service communication:

```toml
[services.ollama]
network_aliases = ["ollama", "llm"]

[services.open-webui]
network_aliases = ["webui", "open-webui"]
```

When aliases are configured:

- The Ollama API is reachable from other containers at `http://ollama:11434` or `http://llm:11434`.
- Open WebUI is reachable at `http://webui:8080` or `http://open-webui:8080`.

This is often cleaner and more portable than hardcoding the Podman host gateway.

## Example: Connecting Open WebUI to Ollama

To connect Open WebUI to Ollama using aliases instead of the host gateway:

```toml
[services.ollama]
network_aliases = ["ollama"]

[services.open-webui.env]
OLLAMA_BASE_URL = "http://ollama:11434"
```

From the host machine, you can still use the published ports:

- Ollama: `http://localhost:11434`
- Open WebUI: `http://localhost:3000`

From containers on the same network, prefer the aliases:

- Ollama: `http://ollama:11434`
- Open WebUI: `http://webui:8080`

## Full Example Configuration

See `example-network-config.toml` at the project root for a complete sample combining `runtime.network`, service ports, volumes, and aliases.
