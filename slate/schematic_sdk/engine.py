"""
SLATE Schematic SDK - Main Engine

Central orchestrator for schematic diagram generation.
Part of SLATE Generative UI protocols.
"""

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from .components import (
    Component, Connection, SchematicConfig, Annotation,
    ServiceNode, DatabaseNode, GPUNode, AINode, APINode,
    QueueNode, ExternalNode, FlowConnector, DashedConnector,
    ComponentStatus, ComponentType
)
from .layout import LayoutEngine, HierarchicalLayout, ForceDirectedLayout, GridLayout, get_layout_engine
from .theme import ThemeManager
from .svg_renderer import SVGRenderer


class SchematicEngine:
    """
    Main schematic generation engine.

    Orchestrates component management, layout calculation, and SVG rendering.
    """

    def __init__(self, config: Optional[SchematicConfig] = None):
        """Initialize the schematic engine."""
        self.config = config or SchematicConfig()
        self.components: List[Component] = []
        self.connections: List[Connection] = []
        self.annotations: List[Annotation] = []
        self.positions: Dict[str, tuple] = {}

        # Initialize theme and renderer
        self.theme_manager = ThemeManager(self.config.theme)
        self.renderer = SVGRenderer(self.theme_manager)

        # Initialize layout engine
        self.layout_engine = get_layout_engine(
            self.config.layout,
            layer_spacing=self.config.layer_spacing,
            node_spacing=self.config.node_spacing
        )

    def add_node(self, component: Component) -> "SchematicEngine":
        """Add a component node to the schematic."""
        self.components.append(component)
        return self

    def add_connector(self, connection: Connection) -> "SchematicEngine":
        """Add a connection between components."""
        self.connections.append(connection)
        return self

    def add_annotation(self, annotation: Annotation) -> "SchematicEngine":
        """Add a text annotation."""
        self.annotations.append(annotation)
        return self

    def set_layout(self, layout_type: str, **kwargs) -> "SchematicEngine":
        """Change layout engine."""
        self.layout_engine = get_layout_engine(layout_type, **kwargs)
        return self

    def set_theme(self, theme_name: str) -> "SchematicEngine":
        """Change theme."""
        self.theme_manager = ThemeManager(theme_name)
        self.renderer = SVGRenderer(self.theme_manager)
        return self

    def apply_layout(self) -> "SchematicEngine":
        """Apply layout algorithm to calculate positions."""
        result = self.layout_engine.calculate_positions(
            self.components,
            self.connections,
            self.config
        )
        self.positions = result.positions
        return self

    def render_svg(self) -> str:
        """Render the schematic to SVG string."""
        # Auto-apply layout if not done
        if not self.positions and self.components:
            self.apply_layout()

        return self.renderer.render(
            components=self.components,
            connections=self.connections,
            positions=self.positions,
            config=self.config,
            annotations=self.annotations if self.annotations else None
        )

    def save(self, path: str, format: str = "svg") -> None:
        """Save schematic to file."""
        svg_content = self.render_svg()

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "svg":
            output_path.write_text(svg_content, encoding="utf-8")
        elif format == "html":
            html_content = self._wrap_in_html(svg_content)
            output_path.write_text(html_content, encoding="utf-8")
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _wrap_in_html(self, svg_content: str) -> str:
        """Wrap SVG in HTML document."""
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.config.title}</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            background: #0D1B2A;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        svg {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }}
    </style>
</head>
<body>
{svg_content}
</body>
</html>'''

    def to_dict(self) -> Dict[str, Any]:
        """Export schematic definition as dictionary."""
        return {
            "config": asdict(self.config),
            "components": [asdict(c) for c in self.components],
            "connections": [asdict(c) for c in self.connections],
            "annotations": [asdict(a) for a in self.annotations],
        }

    def to_json(self) -> str:
        """Export schematic definition as JSON."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SchematicEngine":
        """Create engine from dictionary definition."""
        config = SchematicConfig(**data.get("config", {}))
        engine = cls(config)

        # Add components
        for comp_data in data.get("components", []):
            comp_type = comp_data.get("type", "service")
            comp = cls._create_component(comp_type, comp_data)
            if comp:
                engine.add_node(comp)

        # Add connections
        for conn_data in data.get("connections", []):
            conn = FlowConnector(**conn_data)
            engine.add_connector(conn)

        return engine

    @staticmethod
    def _create_component(comp_type: str, data: Dict[str, Any]) -> Optional[Component]:
        """Create component from type and data."""
        # Remove type field as it's set by the class
        data = {k: v for k, v in data.items() if k != "type"}

        # Convert status string to enum
        if "status" in data and isinstance(data["status"], str):
            data["status"] = ComponentStatus(data["status"])

        type_map = {
            "service": ServiceNode,
            "database": DatabaseNode,
            "gpu": GPUNode,
            "ai": AINode,
            "api": APINode,
            "queue": QueueNode,
            "external": ExternalNode,
        }

        if comp_type in type_map:
            return type_map[comp_type](**data)
        return None


def generate_system_diagram(
    title: str = "System Architecture",
    services: Optional[List[str]] = None,
    connections: Optional[List[tuple]] = None,
    theme: str = "blueprint",
    layout: str = "hierarchical",
    width: int = 900,
    height: int = 600
) -> str:
    """
    Quick function to generate a system diagram.

    Args:
        title: Diagram title
        services: List of service names
        connections: List of (from, to) tuples
        theme: Theme name (blueprint, dark, light)
        layout: Layout algorithm (hierarchical, force, grid)
        width: SVG width
        height: SVG height

    Returns:
        SVG string
    """
    config = SchematicConfig(
        title=title,
        theme=theme,
        layout=layout,
        width=width,
        height=height
    )
    engine = SchematicEngine(config)

    # Add services
    for i, name in enumerate(services or []):
        engine.add_node(ServiceNode(
            id=name.lower().replace(" ", "-"),
            label=name,
            layer=i // 3  # Auto-layer
        ))

    # Add connections
    for from_name, to_name in (connections or []):
        from_id = from_name.lower().replace(" ", "-")
        to_id = to_name.lower().replace(" ", "-")
        engine.add_connector(FlowConnector(
            id=f"{from_id}-to-{to_id}",
            from_node=from_id,
            to_node=to_id
        ))

    return engine.render_svg()


def generate_from_tech_tree(tech_tree_path: str = ".slate_tech_tree/tech_tree.json") -> str:
    """
    Generate schematic from tech tree JSON.

    Args:
        tech_tree_path: Path to tech tree JSON file

    Returns:
        SVG string
    """
    tree_path = WORKSPACE_ROOT / tech_tree_path
    if not tree_path.exists():
        raise FileNotFoundError(f"Tech tree not found: {tree_path}")

    with open(tree_path, encoding="utf-8") as f:
        tree = json.load(f)

    config = SchematicConfig(
        title="SLATE Tech Tree",
        theme="blueprint",
        layout="hierarchical",
        width=1000,
        height=700,
        version_badge=f"v{tree.get('version', '2.0')}"
    )
    engine = SchematicEngine(config)

    # Map status to component status
    status_map = {
        "complete": ComponentStatus.ACTIVE,
        "in_progress": ComponentStatus.PENDING,
        "available": ComponentStatus.INACTIVE,
        "locked": ComponentStatus.INACTIVE,
    }

    # Add nodes
    for node in tree.get("nodes", []):
        status = status_map.get(node.get("status", "available"), ComponentStatus.INACTIVE)
        engine.add_node(ServiceNode(
            id=node["id"],
            label=node["name"],
            sublabel=node.get("description", "")[:30],
            status=status,
            layer=node.get("phase", 1)
        ))

    # Add edges
    for edge in tree.get("edges", []):
        engine.add_connector(FlowConnector(
            id=f"{edge['from']}-to-{edge['to']}",
            from_node=edge["from"],
            to_node=edge["to"]
        ))

    return engine.render_svg()


def generate_from_system_state() -> str:
    """
    Generate schematic from current SLATE system state.

    Returns:
        SVG string
    """
    config = SchematicConfig(
        title="SLATE System Architecture",
        theme="blueprint",
        layout="hierarchical",
        width=900,
        height=600,
        version_badge="v2.5"
    )
    engine = SchematicEngine(config)

    # Layer 0: Presentation
    engine.add_node(ServiceNode(id="dashboard", label="Dashboard", sublabel=":8080", layer=0))
    engine.add_node(ServiceNode(id="cli", label="CLI Tools", sublabel="slate/", layer=0))
    engine.add_node(ServiceNode(id="vscode", label="VS Code", sublabel="@slate", layer=0))
    engine.add_node(AINode(id="claude", label="Claude Code", sublabel="MCP", layer=0))

    # Layer 1: Orchestration
    engine.add_node(ServiceNode(id="router", label="Task Router", layer=1))
    engine.add_node(ServiceNode(id="dispatcher", label="Workflow Dispatcher", layer=1))
    engine.add_node(ServiceNode(id="scheduler", label="GPU Scheduler", layer=1))

    # Layer 2: AI Backends
    engine.add_node(AINode(id="ollama", label="Ollama", sublabel=":11434", layer=2))
    engine.add_node(AINode(id="foundry", label="Foundry Local", sublabel=":5272", layer=2))
    engine.add_node(DatabaseNode(id="chroma", label="ChromaDB", sublabel="Vector Store", layer=2))
    engine.add_node(GPUNode(id="gpu", label="Dual GPU", sublabel="RTX 5070 Ti x2", layer=2))

    # Connections
    engine.add_connector(FlowConnector(id="c1", from_node="dashboard", to_node="router"))
    engine.add_connector(FlowConnector(id="c2", from_node="cli", to_node="router"))
    engine.add_connector(FlowConnector(id="c3", from_node="vscode", to_node="router"))
    engine.add_connector(FlowConnector(id="c4", from_node="claude", to_node="router"))
    engine.add_connector(FlowConnector(id="c5", from_node="router", to_node="dispatcher"))
    engine.add_connector(FlowConnector(id="c6", from_node="router", to_node="scheduler"))
    engine.add_connector(FlowConnector(id="c7", from_node="dispatcher", to_node="ollama"))
    engine.add_connector(FlowConnector(id="c8", from_node="dispatcher", to_node="foundry"))
    engine.add_connector(FlowConnector(id="c9", from_node="scheduler", to_node="gpu"))
    engine.add_connector(FlowConnector(id="c10", from_node="ollama", to_node="chroma"))

    return engine.render_svg()
