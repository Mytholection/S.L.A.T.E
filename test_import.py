#!/usr/bin/env python3
# Modified: 2026-02-06T12:00:00Z | Author: COPILOT | Change: Migrate test from aurora_core to slate
"""Test slate SDK imports to verify installation."""
import sys
sys.path.insert(0, '.')

print("Step 1: Testing basic imports...")
import os
import json
import logging
print("Step 1: OK")

# Test each slate submodule individually
submodules = [
    'slate_status',
    'slate_runtime',
    'slate_benchmark',
    'slate_fork_manager',
    'slate_hardware_optimizer',
    'slate_terminal_monitor',
    'install_tracker',
]

for mod in submodules:
    print(f"Testing slate.{mod}...", flush=True)
    try:
        __import__(f'slate.{mod}')
        print(f"  {mod}: OK")
    except Exception as e:
        print(f"  {mod}: FAIL - {e}")

print("All tests complete!")

