#!/usr/bin/env python3
# Modified: 2026-02-08T01:10:00Z | Author: COPILOT | Change: Create schematic SDK component library
"""
SLATE Schematic SDK - Component Library

Pre-built component definitions and diagram templates for common SLATE
system configurations. These can be used directly or as starting points
for custom diagrams.
"""

from typing import Dict, List, Tuple

from .components import (
    ServiceNode,
    DatabaseNode,
    GPUNode,
    AINode,
    APINode,
    QueueNode,
    ExternalNode,
    FlowConnector,
    DashedConnector,
    DataBus,
    SchematicConfig,
    ComponentStatus,
    Component,
    Connection,
)


# ── Pre-built Node Definitions ───────────────────────────────────────────────

def slate_dashboard(status: ComponentStatus = ComponentStatus.ACTIVE) -> ServiceNode:
    """SLATE Dashboard service node."""
    return ServiceNode(
        id="dashboard",
        label="Dashboard",
        sublabel=":8080",
        status=status,
        layer=0,
    )


def slate_ollama(status: ComponentStatus = ComponentStatus.ACTIVE) -> AINode:
    """Ollama AI inference backend."""
    return AINode(
        id="ollama",
        label="Ollama",
        sublabel=":11434",
        status=status,
        layer=2,
    )


def slate_foundry(status: ComponentStatus = ComponentStatus.ACTIVE) -> AINode:
    """Foundry Local AI backend."""
    return AINode(
        id="foundry",
        label="Foundry Local",
        sublabel=":5272",
        status=status,
        layer=2,
    )


def slate_chromadb(status: ComponentStatus = ComponentStatus.ACTIVE) -> DatabaseNode:
    """ChromaDB vector store."""
    return DatabaseNode(
        id="chromadb",
        label="ChromaDB",
        sublabel="Vector Store",
        status=status,
        layer=2,
    )


def slate_dual_gpu(status: ComponentStatus = ComponentStatus.ACTIVE) -> GPUNode:
    """Dual RTX 5070 Ti GPU cluster."""
    return GPUNode(
        id="gpu-cluster",
        label="Dual GPU",
        sublabel="RTX 5070 Ti x2",
        status=status,
        layer=3,
    )


def slate_gpu(index: int = 0, status: ComponentStatus = ComponentStatus.ACTIVE) -> GPUNode:
    """Single GPU node."""
    return GPUNode(
        id=f"gpu-{index}",
        label=f"GPU {index}",
        sublabel="RTX 5070 Ti 16GB",
        status=status,
        layer=3,
    )


def slate_runner(status: ComponentStatus = ComponentStatus.ACTIVE) -> ServiceNode:
    """GitHub Actions self-hosted runner."""
    return ServiceNode(
        id="runner",
        label="slate-runner",
        sublabel="GitHub Actions",
        status=status,
        layer=1,
    )


def slate_vscode(status: ComponentStatus = ComponentStatus.ACTIVE) -> ServiceNode:
    """VS Code @slate chat participant."""
    return ServiceNode(
        id="vscode",
        label="VS Code",
        sublabel="@slate",
        status=status,
        layer=0,
    )


def slate_claude(status: ComponentStatus = ComponentStatus.ACTIVE) -> AINode:
    """Claude Code MCP integration."""
    return AINode(
        id="claude",
        label="Claude Code",
        sublabel="MCP Server",
        status=status,
        layer=0,
    )


def slate_task_router(status: ComponentStatus = ComponentStatus.ACTIVE) -> ServiceNode:
    """SLATE task routing service."""
    return ServiceNode(
        id="task-router",
        label="Task Router",
        sublabel="Agent Dispatch",
        status=status,
        layer=1,
    )


def slate_workflow_manager(status: ComponentStatus = ComponentStatus.ACTIVE) -> ServiceNode:
    """SLATE workflow management service."""
    return ServiceNode(
        id="workflow-mgr",
        label="Workflow Manager",
        sublabel="Task Lifecycle",
        status=status,
        layer=1,
    )


def github_api(status: ComponentStatus = ComponentStatus.ACTIVE) -> ExternalNode:
    """GitHub API external service."""
    return ExternalNode(
        id="github-api",
        label="GitHub API",
        sublabel="api.github.com",
        status=status,
        layer=0,
    )


def slate_model(name: str, size: str, gpu_index: int = 0) -> AINode:
    """Custom SLATE model node."""
    return AINode(
        id=f"model-{name}",
        label=f"slate-{name}",
        sublabel=f"{size} (GPU {gpu_index})",
        status=ComponentStatus.ACTIVE,
        layer=2,
    )


# ── Diagram Templates ────────────────────────────────────────────────────────

def get_slate_system_template() -> Tuple[List[Component], List[Connection]]:
    """
    Full SLATE system architecture template.

    Returns:
        Tuple of (components, connections) for the full system diagram.
    """
    components: List[Component] = [
        # Layer 0: Interfaces
        slate_dashboard(),
        ServiceNode(id="cli", label="CLI Tools", sublabel="slate/", layer=0),
        slate_vscode(),
        slate_claude(),
        # Layer 1: Orchestration
        slate_task_router(),
        slate_workflow_manager(),
        slate_runner(),
        # Layer 2: AI Backends
        slate_ollama(),
        slate_foundry(),
        slate_chromadb(),
        # Layer 3: Hardware
        slate_dual_gpu(),
    ]

    connections: List[Connection] = [
        FlowConnector(id="c1", from_node="dashboard", to_node="task-router", label="HTTP"),
        FlowConnector(id="c2", from_node="cli", to_node="task-router"),
        FlowConnector(id="c3", from_node="vscode", to_node="task-router", label="LM API"),
        FlowConnector(id="c4", from_node="claude", to_node="task-router", label="MCP"),
        FlowConnector(id="c5", from_node="task-router", to_node="workflow-mgr"),
        FlowConnector(id="c6", from_node="task-router", to_node="runner"),
        FlowConnector(id="c7", from_node="workflow-mgr", to_node="ollama"),
        FlowConnector(id="c8", from_node="workflow-mgr", to_node="foundry"),
        FlowConnector(id="c9", from_node="runner", to_node="ollama"),
        FlowConnector(id="c10", from_node="ollama", to_node="gpu-cluster", label="CUDA"),
        FlowConnector(id="c11", from_node="foundry", to_node="gpu-cluster"),
        DashedConnector(id="c12", from_node="ollama", to_node="chromadb", label="Embed"),
    ]

    return components, connections


def get_ai_inference_template() -> Tuple[List[Component], List[Connection]]:
    """
    AI inference pipeline template with model routing.

    Returns:
        Tuple of (components, connections) for AI inference diagram.
    """
    components: List[Component] = [
        # Clients
        ServiceNode(id="agent", label="SLATE Agent", sublabel="Task Executor", layer=0),
        ServiceNode(id="copilot", label="Copilot Chat", sublabel="@slate", layer=0),
        # Routing
        slate_task_router(),
        # Models
        slate_model("coder", "12B", 0),
        slate_model("fast", "3B", 1),
        slate_model("planner", "7B", 0),
        # Hardware
        slate_gpu(0),
        slate_gpu(1),
        # Storage
        slate_chromadb(),
    ]

    connections: List[Connection] = [
        FlowConnector(id="c1", from_node="agent", to_node="task-router"),
        FlowConnector(id="c2", from_node="copilot", to_node="task-router"),
        FlowConnector(id="c3", from_node="task-router", to_node="model-coder", label="Code Tasks"),
        FlowConnector(id="c4", from_node="task-router", to_node="model-fast", label="Classify"),
        FlowConnector(id="c5", from_node="task-router", to_node="model-planner", label="Plan"),
        FlowConnector(id="c6", from_node="model-coder", to_node="gpu-0", label="CUDA"),
        FlowConnector(id="c7", from_node="model-fast", to_node="gpu-1", label="CUDA"),
        FlowConnector(id="c8", from_node="model-planner", to_node="gpu-0", label="CUDA"),
        DashedConnector(id="c9", from_node="model-coder", to_node="chromadb", label="RAG"),
    ]

    return components, connections


def get_cicd_pipeline_template() -> Tuple[List[Component], List[Connection]]:
    """
    CI/CD pipeline template.

    Returns:
        Tuple of (components, connections) for CI/CD pipeline diagram.
    """
    components: List[Component] = [
        # Triggers
        ExternalNode(id="github", label="GitHub", sublabel="Push/PR", layer=0),
        # Runner
        slate_runner(),
        # Jobs
        ServiceNode(id="lint", label="Lint", sublabel="ruff", layer=2),
        ServiceNode(id="test", label="Test", sublabel="pytest", layer=2),
        ServiceNode(id="sdk-check", label="SDK Validate", sublabel="SLATE SDK", layer=2),
        ServiceNode(id="security", label="Security", sublabel="CodeQL", layer=2),
        AINode(id="ai-test", label="GPU Inference", sublabel="Agentic", layer=2),
        # Output
        ServiceNode(
            id="deploy", label="Deploy", sublabel="CD Pipeline",
            layer=3, status=ComponentStatus.PENDING,
        ),
    ]

    connections: List[Connection] = [
        FlowConnector(id="c1", from_node="github", to_node="runner", label="Webhook"),
        FlowConnector(id="c2", from_node="runner", to_node="lint"),
        FlowConnector(id="c3", from_node="runner", to_node="test"),
        FlowConnector(id="c4", from_node="runner", to_node="sdk-check"),
        FlowConnector(id="c5", from_node="runner", to_node="security"),
        FlowConnector(id="c6", from_node="runner", to_node="ai-test"),
        DashedConnector(id="c7", from_node="test", to_node="deploy", label="Pass"),
    ]

    return components, connections


# ── Template Registry ─────────────────────────────────────────────────────────

TEMPLATES: Dict[str, dict] = {
    "system": {
        "name": "SLATE System Architecture",
        "description": "Full system architecture with all layers",
        "factory": get_slate_system_template,
        "config": SchematicConfig(
            title="SLATE System Architecture",
            width=1000,
            height=700,
            version_badge="v2.5",
        ),
    },
    "inference": {
        "name": "AI Inference Pipeline",
        "description": "Model routing and GPU assignment",
        "factory": get_ai_inference_template,
        "config": SchematicConfig(
            title="SLATE AI Inference Pipeline",
            width=900,
            height=600,
            version_badge="v2.5",
        ),
    },
    "cicd": {
        "name": "CI/CD Pipeline",
        "description": "GitHub Actions workflow pipeline",
        "factory": get_cicd_pipeline_template,
        "config": SchematicConfig(
            title="SLATE CI/CD Pipeline",
            width=900,
            height=600,
        ),
    },
}


def list_templates() -> List[Dict[str, str]]:
    """List available diagram templates."""
    return [
        {"id": k, "name": v["name"], "description": v["description"]}
        for k, v in TEMPLATES.items()
    ]


def build_from_template(template_id: str) -> str:
    """
    Build SVG from a template.

    Args:
        template_id: Template identifier (system, inference, cicd)

    Returns:
        SVG string

    Raises:
        KeyError: If template_id is not found
    """
    if template_id not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        raise KeyError(f"Unknown template: {template_id}. Available: {available}")

    template = TEMPLATES[template_id]
    config = template["config"]
    components, connections = template["factory"]()

    from .engine import SchematicEngine

    engine = SchematicEngine(config)
    for comp in components:
        engine.add_node(comp)
    for conn in connections:
        engine.add_connector(conn)

    return engine.render_svg()
