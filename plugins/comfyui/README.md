# ComfyUI Custom Nodes

This directory contains custom nodes that will be automatically synced to ComfyUI's `custom_nodes` directory when you run `airpods start`.

## Structure

Custom nodes can be in two formats:

### 1. Directory-based packages (recommended)
Directories with an `__init__.py` file:
```
plugins/comfyui/
├── my_custom_node/
│   ├── __init__.py       # Required - marks this as a Python package
│   ├── node.py           # Your node implementation
│   └── requirements.txt  # Optional - node dependencies
```

### 2. Single-file custom nodes
Simple `.py` files placed directly in this directory:
```
plugins/comfyui/
├── simple_node.py
```

## Syncing

Custom nodes are automatically synced when you run:
```bash
airpods start comfyui
```

The sync process:
- Copies all directory-based packages (must have `__init__.py`)
- Copies all single `.py` files
- Removes old custom nodes that no longer exist in source (when `prune=True`)
- Only updates files that have changed (based on modification time)

## Notes

- Custom nodes are copied to `$AIRPODS_HOME/volumes/comfyui_custom_nodes/`
- This directory is mounted into ComfyUI at `/root/ComfyUI/custom_nodes`
- ComfyUI auto-discovers custom nodes on startup
- Directories without `__init__.py` are ignored
- Files/directories starting with `.` or `_` are ignored
