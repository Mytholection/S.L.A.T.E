# /slate-gpu

Manage GPU configuration for SLATE's Ollama LLM backend. Supports single and multi-GPU setups.

## Usage
/slate-gpu [status | configure | preload | balance]

## Instructions

Based on the argument provided (default: status), execute the appropriate command:

**Status (default):**
```powershell
.\.venv\Scripts\python.exe slate/slate_gpu_manager.py --status
```

**Configure GPU(s):**
```powershell
.\.venv\Scripts\python.exe slate/slate_gpu_manager.py --configure
```

**Preload models to GPUs:**
```powershell
.\.venv\Scripts\python.exe slate/slate_gpu_manager.py --preload
```

**JSON output:**
```powershell
.\.venv\Scripts\python.exe slate/slate_gpu_manager.py --json
```

## GPU Layout (auto-configured based on your hardware)
- Single GPU: All models on GPU 0
- Multi-GPU: Heavy models on GPU 0, light models distributed across remaining GPUs

Report the results showing:
1. Per-GPU memory usage and temperature
2. Loaded models and their VRAM consumption
3. Any balancing recommendations
4. Configuration changes made
