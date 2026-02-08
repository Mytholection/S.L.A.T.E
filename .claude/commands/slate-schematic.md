# SLATE Schematic Diagram Generator

Generate circuit-board style system diagrams using the SLATE Schematic SDK.

## Arguments
$ARGUMENTS

## Usage

### Generate from current system state
```bash
.\.venv\Scripts\python.exe -m slate.schematic_sdk.cli from-system --output docs/assets/slate-system-schematic.svg
```

### Generate from tech tree
```bash
.\.venv\Scripts\python.exe -m slate.schematic_sdk.cli from-tech-tree --output docs/assets/tech-tree-schematic.svg
```

### List available components
```bash
.\.venv\Scripts\python.exe -m slate.schematic_sdk.cli components --list
```

### Python SDK usage
```python
from slate.schematic_sdk import (
    SchematicEngine, SchematicConfig,
    ServiceNode, AINode, GPUNode, DatabaseNode,
    FlowConnector
)

# Quick generation
from slate.schematic_sdk import generate_system_diagram
svg = generate_system_diagram(
    title="My System",
    services=["API", "Database", "Cache"],
    connections=[("API", "Database"), ("API", "Cache")]
)

# Full control
config = SchematicConfig(
    title="SLATE Architecture",
    theme="blueprint",
    layout="hierarchical",
    width=900,
    height=600
)
engine = SchematicEngine(config)
engine.add_node(ServiceNode(id="api", label="API Server", sublabel=":8080"))
engine.add_node(DatabaseNode(id="db", label="PostgreSQL"))
engine.add_connector(FlowConnector(from_node="api", to_node="db"))
svg = engine.render_svg()
engine.save("diagram.svg")
```

## Available Components

### Node Types
- `ServiceNode` - Microservice/server (rounded rectangle)
- `DatabaseNode` - Data store (cylinder shape)
- `GPUNode` - GPU/compute resource (hexagon)
- `AINode` - AI/ML service (with brain icon)
- `APINode` - API endpoint
- `QueueNode` - Message queue (parallelogram)
- `ExternalNode` - External service (dashed border)

### Connection Types
- `FlowConnector` - Standard data flow (solid arrow)
- `DashedConnector` - Optional/async flow (dashed arrow)
- `DataBus` - Multi-connection bus

### Layout Algorithms
- `hierarchical` - Layer-based (best for architectures)
- `force` - Physics-based (best for networks)
- `grid` - Grid snap (best for dashboards)

### Themes
- `blueprint` - Dark engineering blueprint (default)
- `dark` - Dark mode with earth tones
- `light` - Light mode for presentations

## Integration Points

### Dashboard API
- `GET /api/schematic/from-system` - Current system state
- `GET /api/schematic/from-tech-tree` - Tech tree diagram
- `POST /api/schematic/generate` - Custom diagram
- `WS /api/schematic/live` - Real-time updates

### MCP Tool
Use `slate_schematic` tool via Claude Code MCP server.

## Part of SLATE Generative UI Protocols
This SDK integrates with SLATE's locked theme (v3.0.0) for consistent visual identity.
