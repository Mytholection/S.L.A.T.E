# /slate-status

Check the status of all SLATE services and system components.

## Usage
/slate-status [--quick | --json | --full]

## Instructions

Run the SLATE status command to check all services:

```powershell
.\.venv\Scripts\python.exe slate/slate_status.py --quick
```

For JSON output (automation):
```powershell
.\.venv\Scripts\python.exe slate/slate_status.py --json
```

For startup script status (services only):
```powershell
.\.venv\Scripts\python.exe slate_startup.py --status
```

Report the results showing:
1. Service status (running/stopped) - Dashboard, Ollama
2. GPU availability and configuration (auto-detected)
3. Python environment validation (3.11+)
4. PyTorch and CUDA status
5. Any warnings or issues detected
6. Recommendations for fixes if issues found
