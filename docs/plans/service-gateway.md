# docs/plans/service-gateway

**STATUS:** PLANNED - NOT IMPLEMENTED

## Purpose

- Add an optional Caddy-based gateway service that sits in front of existing web UIs (initially Open WebUI, later airpods-webui + portal) to provide a single HTTP entrypoint with unified authentication.
- Use the same `AIRPODS_HOME`-driven layout and Podman orchestration that airpods uses for other services, so the gateway is configured and managed like the rest of the stack.
- Keep airpods focused on orchestration; Caddy handles auth/TLS/routing via forward authentication to Open WebUI's JWT system, while the web UIs remain responsible for their own feature surfaces.

## Role In The Stack

- Runs as a Podman-managed service (`gateway`/`caddy`) controlled by `airpods init/start/stop/status/logs` alongside Ollama, Open WebUI, and future web UIs.
- Default host exposure: only Open WebUI is host-facing; all other services (Ollama, ComfyUI, etc.) stay on the internal Podman network.
- When enabled, the gateway fronts the host entrypoint and hides Open WebUI behind a single port:
  - Browser → `localhost:<gateway_port>` → Caddy (auth check) → internal Open WebUI.
- Auth posture:
  - **Forward Auth to Open WebUI**: Caddy delegates authentication to Open WebUI's existing JWT/session system via `forward_auth` directive.
  - **Single Sign-On Experience**: Users log in once via Open WebUI's native login (proxied through Caddy); all subsequent requests are validated by Caddy calling Open WebUI's `/api/v1/users/me` endpoint.
  - **No credential duplication**: Leverages Open WebUI's user database, password hashing (bcrypt), and session management without reimplementing auth logic.
  - **Optional Basic Auth layer**: For additional security, Basic Auth can be layered on top for `/portal` admin routes while chat routes use Open WebUI auth only.
- Remains optional: for purely local, single-user setups Caddy can be disabled and users can continue to hit Open WebUI directly.

## Capabilities

### Phase 1: Forward Auth MVP (Open WebUI Integration)
- **Unified authentication**:
  - Caddy uses `forward_auth` to delegate authentication to Open WebUI's JWT/session verification.
  - Every protected request triggers Caddy to call `http://open-webui:8080/api/v1/users/me` with forwarded `Cookie` and `Authorization` headers.
  - Open WebUI validates JWT signature (using `WEBUI_SECRET_KEY`), checks expiration, and verifies user exists in database.
  - If valid (HTTP 200), Caddy proxies request; if invalid (401/403), Caddy blocks access.
- **Login flow**:
  - `/api/v1/auths/*` and `/auth/*` routes bypass forward auth to allow login form access.
  - Users authenticate via Open WebUI's native login (username/password, OAuth, LDAP).
  - Open WebUI issues JWT token (via `Authorization: Bearer` header or HTTP-only cookie).
  - Caddy caches auth context for duration of session.
- **Security benefits**:
  - Single HTTP port exposed to host (`gateway_port`, e.g., 8080).
  - Open WebUI port (3000) bound only to internal Podman network (`open-webui:8080`).
  - All authentication logic remains in Open WebUI (no credential sync, no password files).
  - Leverages existing Open WebUI features: password hashing (bcrypt), session management, user roles.

### Phase 2: Portal/Admin Protection (Future)
- **Two-tier auth model**:
  - `/chat` routes: Forward auth to Open WebUI (regular user login).
  - `/portal` routes: Optional Basic Auth layer for admin access (using `auth_secret` from `AIRPODS_HOME/configs/`).
- **Airpods-webui integration**:
  - Positions Caddy as edge proxy for unified airpods-webui backend serving both chat and portal.
  - Handles TLS termination and route-specific authentication policies.
- **Advanced auth options** (stretch goals):
  - OIDC/OAuth integration via Caddy plugins (e.g., `caddy-security`).
  - External IdP support for enterprise deployments.
  - JWT validation directly in Caddy using `caddy-jwt` plugin (requires secret sync with Open WebUI).

## Service Architecture

### Phase 1: Gateway Service Spec (Open WebUI Forward Auth)
```toml
[services.gateway]
enabled = false  # Opt-in feature
image = "docker.io/caddy:2.8-alpine"
pod = "gateway"
container = "caddy-0"
network_aliases = ["gateway", "caddy"]
ports = [
  { host = 8080, container = 80 }
]
volumes = {
  config = {
    source = "bind://gateway/Caddyfile",
    target = "/etc/caddy/Caddyfile",
    readonly = true
  },
  data = {
    source = "bind://gateway/data",
    target = "/data"
  }
}
health = { path = "/", expected_status = [200, 399] }
env = {}
needs_webui_secret = false  # Auth delegated to Open WebUI
```

**Caddyfile Template** (`$AIRPODS_HOME/volumes/gateway/Caddyfile`):
```caddyfile
{
  # Global options
  auto_https off
  admin off
}

:80 {
  # Allow Open WebUI login routes (bypass forward auth)
  @login {
    path /api/v1/auths/* /auth/*
  }
  handle @login {
    reverse_proxy open-webui:8080
  }
  
  # Forward auth for all other routes
  @protected {
    not path /api/v1/auths/* /auth/*
  }
  handle @protected {
    forward_auth open-webui:8080 {
      uri /api/v1/users/me
      copy_headers Cookie Authorization
    }
    reverse_proxy open-webui:8080
  }
}
```

### Phase 2: Unified Backend with Portal (Future)
```caddyfile
:80 {
  # Login routes (no auth)
  handle /api/v1/auths/* {
    reverse_proxy open-webui:8080
  }
  
  # Admin portal (optional Basic Auth + forward auth)
  handle /portal/* {
    basicauth {
      airpods {env.AUTH_SECRET_HASH}
    }
    forward_auth open-webui:8080 {
      uri /api/v1/users/me
      copy_headers Cookie Authorization
    }
    reverse_proxy airpods-webui:8000
  }
  
  # Chat routes (forward auth only)
  handle /* {
    forward_auth open-webui:8080 {
      uri /api/v1/users/me
      copy_headers Cookie Authorization
    }
    reverse_proxy open-webui:8080
  }
}
```

**Port Binding Changes When Gateway Enabled**:
- Open WebUI: Remove host bind, only expose on `airpods_network` (internal `open-webui:8080`).
- Gateway: Bind `localhost:8080:80` (or user-configured `gateway_port`).
- ComfyUI/other services: Remain internal-only unless explicitly exposed.

## Configuration Patterns (As Described)

- **AIRPODS_HOME and layout**:
  - `AIRPODS_HOME` is resolved by a helper (described in the gateway MVP plan) using:
    - `AIRPODS_HOME` env var if set.
    - `<repo-root>/config` during development.
    - A user home directory path such as `~/.airpods` for installed/production use.
  - Relevant files under `AIRPODS_HOME`:
    - `webui_secret` – existing Open WebUI secret (planned elsewhere).
    - `auth_secret` – new opaque shared secret used as the Basic Auth password.
    - `caddy/Caddyfile` – generated Caddy configuration file.
- **Secrets and helpers**:
  - Gateway plan defines helpers such as:
    - `get_auth_secret_path(home: Path) -> Path`.
    - `ensure_auth_secret(home: Path) -> str`:
      - Reads `<HOME>/auth_secret` if it exists; otherwise generates a new random secret, writes it with restrictive permissions (e.g. `0600`), and returns it.
  - `airpods init` and `airpods start` are expected to call `ensure_auth_secret` so the gateway always has a password to use.
- **Auth configuration knobs**:
  - Gateway MVP plan calls for configuration fields like:
    - `auth_enabled: bool` – whether to run Caddy and hide Open WebUI behind it.
    - `auth_port: int` – the host port on which the gateway listens.
    - (Later) `auth_username: str` – defaults to `airpods` in the MVP plan.
  - Portal/auth plan further suggests configuration that controls:
    - Whether `/chat` is protected or just `/portal`.
    - Credentials when Basic Auth is used.
    - When more advanced auth (such as OIDC) is enabled.
- **Caddyfile templates**:
  - Gateway MVP plan describes a minimal Caddyfile that:
    - Listens on `:auth_port`.
    - Uses `basicauth` with username `airpods` and the `auth_secret` value as the password.
    - Reverse proxies all requests to `open-webui:8080` on the internal network.
  - Portal/auth plan describes a similar template oriented around airpods-webui:
    - Proxies `/chat` and `/portal` to a single backend.
    - Optionally proxies to Open WebUI at a separate path.
    - Enables Basic Auth for `/portal` and, optionally, `/chat`.

## How It Serves Airpods Goals

- **Single orchestrated entrypoint**:
  - Airpods remains responsible for starting containers and wiring networks and volumes; the gateway service becomes another managed container in the dependency graph.
  - With gateway enabled, users access the web stack through one predictable URL (`http://localhost:8080`) instead of service-specific ports.
- **Safe-by-default behavior**:
  - When `gateway.enabled = true`, Open WebUI is no longer bound directly to the host; Caddy is the only host-facing surface for web UIs.
  - Authentication remains centralized in Open WebUI's database (no credential duplication, no plaintext password files).
  - Secrets and configs live under `AIRPODS_HOME/configs` and `AIRPODS_HOME/volumes`, keeping runtime assets grouped together.
- **Config- and template-driven design**:
  - Gateway service spec follows same pattern as Ollama/Open WebUI/ComfyUI (TOML config with template variables).
  - Caddyfile generated dynamically during `airpods start` using existing template resolver (`{{services.*.ports.*}}`).
  - Port binding logic conditional on `gateway.enabled` flag (no hard-coded paths).
- **Zero Open WebUI code changes**:
  - Leverages Open WebUI's existing `/api/v1/users/me` endpoint for session validation.
  - No custom auth middleware, no API keys, no credential sync.
  - Works with Open WebUI's built-in authentication methods (password, OAuth, LDAP).

## Utility As A Service

- **Securing and hiding internal services**:
  - Caddy allows Open WebUI (and later airpods-webui + portal) to run on an internal network address only (`open-webui:8080` on `airpods_network`).
  - Gateway controls what is reachable from the host and enforces authentication before proxying requests.
  - For local setups accessible on a LAN, gateway provides centralized access control without modifying service containers.
- **Single sign-on across services**:
  - Users log in once via Open WebUI's login form (username/password).
  - JWT token issued by Open WebUI is validated by Caddy for all subsequent requests.
  - Future services (airpods-webui portal, ComfyUI with auth, etc.) can leverage same session via forward auth.
- **Foundation for advanced auth**:
  - Forward auth pattern supports evolution:
    - **Phase 1**: JWT validation via Open WebUI API call.
    - **Phase 2**: Optional Basic Auth layer for admin routes (`/portal`).
    - **Phase 3**: OIDC/OAuth integration via Caddy plugins (enterprise scenarios).
  - Caddy config can be extended without modifying Python backend or service containers.
  - TLS termination and certificate management handled by Caddy (Let's Encrypt, self-signed, etc.).
- **Supporting different usage modes**:
  - **Disabled gateway** (default): Direct access to Open WebUI at `localhost:3000`, ComfyUI at `localhost:8188`, etc. (current behavior).
  - **Enabled gateway**: Single entrypoint at `localhost:8080` with unified auth; internal services unreachable from host.
  - **Partial gateway**: Gateway fronts Open WebUI only; other services remain directly accessible (mixed mode).

## Interaction With Service-Specific Auth

- **Open WebUI**:
  - Open WebUI maintains its own user accounts and login/session model; the gateway does not replace or manage that internal auth.
  - When the gateway is enabled in front of Open WebUI, the effective flow is “(optional) gateway Basic Auth → Open WebUI login”. By default, rely on Open WebUI login as the primary gate.
- **Services without their own auth in these plans**:
  - For services that are treated as local-only in the current plans (such as a ComfyUI deployment or the llama.cpp native WebUI), the gateway’s Basic Auth can act as the primary username/password protection in front of their HTTP endpoints.
  - This lets users benefit from a simple shared login even when a given UI does not have its own account system configured within airpods.
- **Optional and per-setup choice**:
  - Because the gateway itself is optional, users can decide whether they want an extra password gate in front of Open WebUI or rely solely on Open WebUI’s own auth.
  - Future configuration extensions can build on this pattern by allowing more granular control over which routes are protected by gateway-level auth versus service-level auth.

## Implementation Roadmap

### Phase 1: Forward Auth MVP (Current Branch)
**Goal**: Enable gateway with Open WebUI forward authentication.

**Code Changes**:
1. **Configuration** (`airpods/configuration/`):
   - Add `gateway` service to `defaults.py` (disabled by default)
   - Schema validation for gateway service spec
   - Template resolver support for Caddyfile generation

2. **State Management** (`airpods/state.py`):
   ```python
   def gateway_caddyfile_path() -> Path:
       return volumes_dir() / "gateway" / "Caddyfile"
   
   def ensure_gateway_caddyfile(content: str) -> Path:
       path = gateway_caddyfile_path()
       path.parent.mkdir(parents=True, exist_ok=True)
       path.write_text(content, encoding="utf-8")
       return path
   ```

3. **Service Manager** (`airpods/services.py`):
   - Dynamic port binding for Open WebUI based on `gateway.enabled` flag
   - Logic: if gateway enabled, set `open-webui.ports = []` (internal only)
   - Gateway starts after Open WebUI is healthy

4. **Start Command** (`airpods/cli/commands/start.py`):
   ```python
   # After Open WebUI health check passes
   if gateway_enabled:
       caddyfile_template = load_caddyfile_template()
       resolved_content = resolver.resolve(caddyfile_template)
       state.ensure_gateway_caddyfile(resolved_content)
       manager.start_service(gateway_spec)
       console.print("[ok]Gateway started at http://localhost:8080[/]")
   ```

5. **Caddyfile Template** (`configs/Caddyfile.template`):
   ```caddyfile
   {
     auto_https off
     admin off
   }
   
   :{{services.gateway.ports.0.container}} {
     @login path /api/v1/auths/* /auth/*
     handle @login {
       reverse_proxy open-webui:{{services.open-webui.ports.0.container}}
     }
     
     @protected not path /api/v1/auths/* /auth/*
     handle @protected {
       forward_auth open-webui:{{services.open-webui.ports.0.container}} {
         uri /api/v1/users/me
         copy_headers Cookie Authorization
       }
       reverse_proxy open-webui:{{services.open-webui.ports.0.container}}
     }
   }
   ```

6. **Status/Logs/Stop Commands**:
   - Gateway appears in `airpods status` output
   - `airpods logs gateway` works like other services
   - `airpods stop` includes gateway in shutdown sequence

**Testing**:
- Unit tests for Caddyfile generation and template resolution
- Integration test: start with `gateway.enabled = true`, verify port bindings
- Manual test: login via gateway, confirm forward auth works

### Phase 2: Portal Admin Routes (Future)
**Goal**: Add `/portal` admin interface with optional Basic Auth layer.

**Changes**:
- `airpods-webui` backend serving both `/chat` (proxied Open WebUI) and `/portal` (orchestration UI)
- Caddyfile extended with Basic Auth for `/portal/*` routes
- `auth_secret` helper added to `state.py` for Basic Auth password generation
- Configuration option: `gateway.portal_auth_enabled` (default: true)

### Phase 3: Advanced Auth (Stretch Goals)
- TLS certificate management via Caddy (Let's Encrypt, self-signed)
- OIDC integration using `caddy-security` plugin
- Multi-backend routing (Open WebUI, ComfyUI, custom services)
- Rate limiting and access logs

## Summary

- The gateway service is an optional, Caddy-based edge layer that:
  - Provides a single HTTP entrypoint in front of Open WebUI (and later airpods-webui + portal).
  - Uses `AIRPODS_HOME` to store its secrets and Caddyfile, mirroring production layouts.
  - Applies Basic Auth in the MVP using an `auth_secret` file, with room to grow into more advanced auth.
  - Is managed like any other airpods service via Podman, keeping airpods in its role as an orchestrator rather than a web server or auth provider.
- Together, the gateway/auth plans define how this service can secure, hide, and route access to the local AI stack without changing the core CLI’s responsibilities.
