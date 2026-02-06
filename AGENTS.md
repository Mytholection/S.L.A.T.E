# S.L.A.T.E. Agent Instructions

## Overview
SLATE (System Learning Agent for Task Execution) codebase.

## Format Rules
All code edits require timestamp + author:
```python
# Modified: YYYY-MM-DDTHH:MM:SSZ | Author: COPILOT | Change: description
```

## Commands
```bash
python aurora_core/slate_status.py --quick
python aurora_core/slate_runtime.py --check-all
python aurora_core/slate_hardware_optimizer.py
```

## Security
- All operations LOCAL ONLY (127.0.0.1)
- No external telemetry
