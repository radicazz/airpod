# docs/plans/service-llama

**STATUS:** PLANNED - NOT IMPLEMENTED

## Purpose

- Add llama.cpp as an optional, first-class service in airpods alongside Ollama, Open WebUI, and ComfyUI.
- Use llama.cpp as the dedicated GGUF runtime (OpenAI-style HTTP APIs, CPU/GPU execution) so ComfyUI can consume LLMs via HTTP instead of Python bindings.
- Keep airpods focused on orchestration: containers, pods, volumes, networks, and configuration; llama.cpp remains the model runtime.

## Role In The Stack

- Runs as an additional service that airpods can `start`, `stop`, `status`, and `logs`, just like Ollama and Open WebUI.
- Exposes an OpenAI-compatible HTTP API (via `llama-server`) for:
  - Open WebUI (OpenAI backend config)
  - ComfyUI custom nodes (HTTP client)
- Replaces the need to embed `llama-cpp-python` into the ComfyUI container image, reducing image complexity and GPU build risk.
- Stores GGUF models in a dedicated volume (`airpods_models/gguf`) that is not shared with Ollama’s internal storage format.

## Concrete Service Decisions (Implementation-Ready)

- **Service name**: `llamacpp`
- **Image defaults** (configurable):
  - CPU: `ghcr.io/ggerganov/llama.cpp:server`
  - GPU (CUDA): `ghcr.io/ggerganov/llama.cpp:server-cuda`
- **Container command**: `llama-server` with config-driven `command_args`
- **Container port**: `8080` (llama.cpp default)
- **Default host port**: `11435` (avoids Ollama’s `11434` and common web ports)
- **Health check**: HTTP `GET /health` expecting `200-299`
- **Enabled by default**: `false` (opt-in to avoid changing default `airpods start` behavior)

Note: If the upstream image changes health path or port, the plan expects a config override rather than code changes.

## Configuration Schema Extensions

Extend `ServiceConfig` with:

- `command_args`: `Dict[str, CommandArg]`
  - `CommandArg = str | int | float | bool | List[str | int | float]`
- `entrypoint_override`: `Optional[List[str]]`
- `default_model`: `Optional[str]` (default GGUF file name or relative path under `/models`)

### Rendering Rules For `command_args`

Given TOML:

```toml
command_args = { model = "/models/{{services.llamacpp.default_model}}", ctx_size = 4096, n_gpu_layers = 40, threads = 8, port = 8080, host = "0.0.0.0", log_disable = true }
```

Render into CLI flags:

- Keys are converted from snake_case to kebab-case: `ctx_size` → `--ctx-size`
- Booleans:
  - `true` → include flag with no value (`--log-disable`)
  - `false` → omit flag entirely
- Lists: repeat the flag for each entry (preserve order)
  - `stop = ["\n\n", "###"]` → `--stop "\n\n" --stop "###"`
- Numbers and strings: render as `--key value` using shell-safe argument arrays (no extra quoting in the config)
- Ordering: preserve TOML insertion order

`entrypoint_override` (if provided) replaces the default `llama-server` entrypoint.

## Default Config Block (Example)

```toml
[services.llamacpp]
enabled = false
image = "ghcr.io/ggerganov/llama.cpp:server"
pod = "llamacpp"
container = "llamacpp-0"
ports = [{ host = 11435, container = 8080 }]
volumes = { models = { source = "bind://airpods_models/gguf", target = "/models" } }
health = { path = "/health", expected_status = [200, 299] }
needs_webui_secret = false

default_model = "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
command_args = { model = "/models/{{services.llamacpp.default_model}}", ctx_size = 4096, n_gpu_layers = 40, threads = 8, port = 8080, host = "0.0.0.0" }
```

To enable GPU:

```toml
[services.llamacpp.gpu]
enabled = true
force_cpu = false
```

To force CPU:

```toml
[services.llamacpp.gpu]
enabled = false
force_cpu = true
```

## Volumes & Paths

- Bind-mounted GGUF store: `bind://airpods_models/gguf` → `$AIRPODS_HOME/volumes/airpods_models/gguf`
- Container mount: `/models`

This keeps GGUF artifacts separate from Ollama and ComfyUI models.

## Runtime + GPU Behavior

- `get_runtime(prefer)` still selects Podman or Docker.
- GPU flags are injected via existing `gpu.py` and per-runtime adapters.
- `cuda_version` from config should select the `server-cuda` image when `gpu.enabled = true`.
- If GPU detection fails and `force_cpu = false`, emit a warning and fall back to CPU image.

## CLI Behavior Updates

- `start`:
  - Accepts `llamacpp` as a service name (and alias `llama`, `llama-cpp`, `llama.cpp`).
  - Creates the GGUF bind directory if missing.
  - Pulls the `llamacpp` image.
  - Uses `command_args` rendering to build the container command.
  - Waits for `/health` to return 2xx unless `health.path` is unset.
- `stop`:
  - Stops `llamacpp` gracefully; preserves the GGUF volume.
- `status`:
  - Shows URL `http://localhost:11435` (or configured host port) and health status.
- `logs`:
  - Tails `llamacpp` container logs.
- `doctor`:
  - Validates llama.cpp image availability, port conflicts, and models path permissions.
- `clean`:
  - Removes `airpods_models/gguf` when `--volumes` or `--all` is used.
- `backup` / `restore`:
  - Include GGUF metadata directory (config + model index files if present), not the GGUF model binaries unless `--include-models` is explicitly added later.
- `config validate`:
  - Enforces that `command_args.model` is present or `default_model` is set.

## Models Command Extension

Add a GGUF scope to `models` without changing existing Ollama behavior:

- `airpods models gguf pull <url> [--name <filename>]` → downloads into `airpods_models/gguf`
- `airpods models gguf list` → lists `*.gguf` in the GGUF store with sizes
- `airpods models gguf remove <filename>` → deletes from GGUF store

If a separate command is preferred, introduce `airpods gguf` with the same subcommands.

## ComfyUI Integration

- Custom node package: `plugins/comfyui/airpods_gguf/`
- Node uses llama.cpp HTTP endpoints and returns text to downstream nodes.
- Required config/env to reach the service:
  - `AIRPODS_LLAMACPP_URL` defaulting to `http://localhost:11435/v1`

See `docs/plans/custom_node_llama.md` for full node design.

## Testing Suggestions

- Unit tests:
  - `command_args` rendering + template resolution
  - service selection (CPU/GPU image)
  - `models gguf` path handling
  - `doctor` llama.cpp checks
- Manual checks:
  - `airpods start llamacpp`
  - Health endpoint returns OK
  - ComfyUI custom node can chat via llama.cpp

## Summary

- llama.cpp becomes the dedicated GGUF LLM runtime service.
- ComfyUI consumes LLMs via a custom node that calls llama.cpp’s OpenAI-style HTTP API.
- No dependency on Ollama’s on-disk format; GGUF storage is separate and explicit.
- This reduces ComfyUI image complexity while keeping airpods’ orchestration role intact.
