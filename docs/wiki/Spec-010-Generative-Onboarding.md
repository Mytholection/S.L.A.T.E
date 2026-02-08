# Spec 010: Generative Onboarding
<!-- Modified: 2026-02-08T00:00:00Z | Author: CLAUDE | Change: Create wiki page for Generative Onboarding -->

**Status**: Completed
**Created**: 2026-02-07
**Depends On**: spec-008 (Guided Experience)

## Overview

Generative Onboarding extends the Guided Experience (Spec 008) with AI-generated installation and setup flows. The system dynamically generates onboarding steps based on the user's hardware, existing configuration, and detected environment.

## Key Features

### Dynamic Step Generation

The onboarding flow adapts to what's already installed:

| Detection | Generated Steps |
|-----------|-----------------|
| No Python | Install Python, create venv |
| Python found | Skip to venv creation |
| GPU detected | Include GPU optimization steps |
| CPU-only | Configure CPU-only mode |
| Ollama running | Skip Ollama installation |

### Interactive Experience UI

Provides a real-time dashboard view of the onboarding progress:

- Hardware detection results
- Installation progress bars
- Error recovery suggestions
- Skip/retry options for each step

### Generative UI Protocols

The onboarding uses SLATE's Generative UI system:

```python
from slate.slate_generative_ui import GenerativeUIManager

manager = GenerativeUIManager()
experience = manager.create_experience("onboarding")
experience.detect_environment()
experience.generate_steps()
experience.execute()
```

## Implementation

### Environment Detection

```python
# Automatic detection of:
# - OS and version
# - Python version and venv status
# - GPU hardware (NVIDIA, AMD, Apple Silicon)
# - Installed AI backends (Ollama, Foundry)
# - VS Code and extensions
# - Git configuration
```

### Step Types

| Type | Description |
|------|-------------|
| `detection` | Environment scanning |
| `installation` | Package/tool installation |
| `configuration` | Settings and config files |
| `verification` | Health checks and validation |
| `celebration` | Success confirmation |

## Files

- `slate/slate_generative_ui.py` - Core generative UI engine
- `slate_web/interactive_experience_ui.py` - Dashboard UI components

## Related Specifications

- [Spec 008: Guided Experience](Spec-008-Guided-Experience)
- [Spec 009: Copilot Roadmap Awareness](Spec-009-Copilot-Roadmap-Awareness)
