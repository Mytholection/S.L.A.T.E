"""
SLATE Schematic Diagram Generation SDK

Circuit-board style diagram generation for system visualization.
Part of SLATE Generative UI protocols.

Usage:
    from slate.schematic_sdk import (
        SchematicEngine, SchematicConfig,
        ServiceNode, AINode, GPUNode, DatabaseNode,
        FlowConnector, DashedConnector,
        generate_system_diagram, generate_from_tech_tree
    )

    # Quick generation
    svg = generate_system_diagram(
        title="My System",
        services=["API", "Database", "Cache"],
        connections=[("API", "Database"), ("API", "Cache")]
    )

    # Full control
    engine = SchematicEngine(SchematicConfig(title="Architecture"))
    engine.add_node(ServiceNode(id="api", label="API Server"))
    engine.add_node(DatabaseNode(id="db", label="PostgreSQL"))
    engine.add_connector(FlowConnector(from_node="api", to_node="db"))
    svg = engine.render_svg()
"""

from .components import (
    # Config
    SchematicConfig,

    # Enums
    ComponentType,
    ComponentStatus,
    ConnectionStyle,
    PortPosition,

    # Base classes
    Component,
    Connection,
    Port,
    Annotation,
    Layer,

    # Node components
    ServiceNode,
    DatabaseNode,
    GPUNode,
    AINode,
    APINode,
    QueueNode,
    ExternalNode,

    # Connection components
    FlowConnector,
    DashedConnector,
    DataBus,

    # Terminal components
    InputTerminal,
    OutputTerminal,
)

from .layout import (
    LayoutEngine,
    LayoutResult,
    HierarchicalLayout,
    ForceDirectedLayout,
    GridLayout,
    get_layout_engine,
)

from .theme import (
    ThemeManager,
    SchematicTheme,
    SchematicColors,
    SchematicTypography,
    SchematicEffects,
    BlueprintTheme,
    DarkTheme,
    LightTheme,
)

from .svg_renderer import SVGRenderer

from .engine import (
    SchematicEngine,
    generate_system_diagram,
    generate_from_tech_tree,
    generate_from_system_state,
)

# Modified: 2026-02-08T01:25:00Z | Author: COPILOT | Change: Add library and exporter imports
from .library import (
    TEMPLATES,
    build_from_template,
    list_templates,
    get_slate_system_template,
    get_ai_inference_template,
    get_cicd_pipeline_template,
    slate_dashboard,
    slate_ollama,
    slate_foundry,
    slate_chromadb,
    slate_dual_gpu,
    slate_gpu,
    slate_runner,
    slate_vscode,
    slate_claude,
    slate_task_router,
    slate_workflow_manager,
    github_api,
    slate_model,
)

from .exporters import (
    SVGExporter,
    HTMLExporter,
    Base64Exporter,
    MarkdownExporter,
    JSONExporter,
)

__version__ = "1.1.0"
__all__ = [
    # Config
    "SchematicConfig",

    # Enums
    "ComponentType",
    "ComponentStatus",
    "ConnectionStyle",
    "PortPosition",

    # Base classes
    "Component",
    "Connection",
    "Port",
    "Annotation",
    "Layer",

    # Node components
    "ServiceNode",
    "DatabaseNode",
    "GPUNode",
    "AINode",
    "APINode",
    "QueueNode",
    "ExternalNode",

    # Connection components
    "FlowConnector",
    "DashedConnector",
    "DataBus",

    # Terminal components
    "InputTerminal",
    "OutputTerminal",

    # Layout
    "LayoutEngine",
    "LayoutResult",
    "HierarchicalLayout",
    "ForceDirectedLayout",
    "GridLayout",
    "get_layout_engine",

    # Theme
    "ThemeManager",
    "SchematicTheme",
    "SchematicColors",
    "SchematicTypography",
    "SchematicEffects",
    "BlueprintTheme",
    "DarkTheme",
    "LightTheme",

    # Renderer
    "SVGRenderer",

    # Engine
    "SchematicEngine",
    "generate_system_diagram",
    "generate_from_tech_tree",
    "generate_from_system_state",

    # Library
    "TEMPLATES",
    "build_from_template",
    "list_templates",
    "get_slate_system_template",
    "get_ai_inference_template",
    "get_cicd_pipeline_template",
    "slate_dashboard",
    "slate_ollama",
    "slate_foundry",
    "slate_chromadb",
    "slate_dual_gpu",
    "slate_gpu",
    "slate_runner",
    "slate_vscode",
    "slate_claude",
    "slate_task_router",
    "slate_workflow_manager",
    "github_api",
    "slate_model",

    # Exporters
    "SVGExporter",
    "HTMLExporter",
    "Base64Exporter",
    "MarkdownExporter",
    "JSONExporter",
]
