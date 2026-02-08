# Spec 011: Schematic Diagram SDK
<!-- Modified: 2026-02-08T00:00:00Z | Author: CLAUDE | Change: Create wiki page for Schematic SDK -->

**Status**: Completed
**Created**: 2026-02-08
**Depends On**: spec-007 (Design System)

## Overview

The Schematic Diagram SDK provides circuit-board style architecture visualizations for SLATE. It generates SVG diagrams showing system components, connections, and data flows with a blueprint aesthetic.

## Key Components

### Node Types

| Node Type | Shape | Purpose |
|-----------|-------|---------|
| `ServiceNode` | Rounded rectangle | Microservices, servers |
| `DatabaseNode` | Cylinder | Data stores, caches |
| `GPUNode` | Hexagon | GPU/compute resources |
| `AINode` | Diamond | AI/ML components |
| `QueueNode` | Parallelogram | Message queues |
| `ExternalNode` | Cloud shape | External services |

### Connection Types

| Connection | Style | Purpose |
|------------|-------|---------|
| `FlowConnector` | Solid line | Primary data flow |
| `DashedConnector` | Dashed line | Optional/async flow |
| `DataBus` | Thick line | High-throughput channels |

## Usage

### Quick Generation

```python
from slate.schematic_sdk import generate_system_diagram

svg = generate_system_diagram(
    title="My System",
    services=["API", "Database", "Cache"],
    connections=[("API", "Database"), ("API", "Cache")]
)
```

### Full Control

```python
from slate.schematic_sdk import (
    SchematicEngine, SchematicConfig,
    ServiceNode, DatabaseNode, FlowConnector
)

engine = SchematicEngine(SchematicConfig(title="Architecture"))
engine.add_node(ServiceNode(id="api", label="API Server"))
engine.add_node(DatabaseNode(id="db", label="PostgreSQL"))
engine.add_connector(FlowConnector(from_node="api", to_node="db"))
svg = engine.render_svg()
```

## Theme System

The SDK includes three built-in themes:

| Theme | Description |
|-------|-------------|
| `BlueprintTheme` | Technical blue with grid lines (default) |
| `DarkTheme` | SLATE dark surface with copper accents |
| `LightTheme` | Light mode for documentation |

## Export Formats

| Exporter | Output |
|----------|--------|
| `SVGExporter` | Raw SVG file |
| `HTMLExporter` | Standalone HTML page |
| `Base64Exporter` | Data URI for inline embedding |
| `MarkdownExporter` | Markdown-compatible format |
| `JSONExporter` | Manifest with metadata |

## CLI Usage

```bash
# Generate system diagram
python -m slate.schematic_sdk.cli --system --output diagram.svg

# Generate from tech tree
python -m slate.schematic_sdk.cli --tech-tree --output tree.svg

# List available templates
python -m slate.schematic_sdk.cli --list-templates
```

## Files

- `slate/schematic_sdk/__init__.py` - Package exports
- `slate/schematic_sdk/engine.py` - Main generation engine
- `slate/schematic_sdk/components.py` - Node and connection classes
- `slate/schematic_sdk/theme.py` - Theme definitions
- `slate/schematic_sdk/layout.py` - Layout algorithms
- `slate/schematic_sdk/svg_renderer.py` - SVG generation
- `slate/schematic_sdk/library.py` - Pre-built templates
- `slate/schematic_sdk/exporters.py` - Export handlers

## Related Specifications

- [Spec 007: Design System](Spec-007-Design-System)
- [Spec 012: Schematic GUI Layout](Spec-012-Schematic-GUI-Layout)
