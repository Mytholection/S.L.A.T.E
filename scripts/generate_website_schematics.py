# Modified: 2026-02-08T01:05:00Z | Author: COPILOT | Change: Add timestamp for SLATE commit hook
"""
SLATE Website Schematic Generator

Generates comprehensive system schematics for the GitHub Pages website.
These schematics are also used in the dashboard.
"""

import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from slate.schematic_sdk.engine import SchematicEngine
from slate.schematic_sdk.components import (
    SchematicConfig, ServiceNode, DatabaseNode, GPUNode, AINode,
    APINode, QueueNode, ExternalNode, FlowConnector, DashedConnector,
    ComponentStatus, Annotation
)


def generate_complete_architecture() -> str:
    """Generate the complete SLATE system architecture schematic."""
    config = SchematicConfig(
        title="S.L.A.T.E. System Architecture",
        theme="blueprint",
        layout="hierarchical",
        width=1100,
        height=750,
        version_badge="v2.5",
        layer_spacing=140,
        node_spacing=90
    )
    engine = SchematicEngine(config)

    # Layer 0: User Interfaces
    engine.add_node(ServiceNode(
        id="dashboard", label="Dashboard", sublabel="localhost:8080",
        layer=0, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="cli", label="CLI Tools", sublabel="slate/*.py",
        layer=0, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="vscode", label="VS Code", sublabel="@slate Extension",
        layer=0, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(AINode(
        id="claude", label="Claude Code", sublabel="MCP Server",
        layer=0, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ExternalNode(
        id="copilot", label="GitHub Copilot", sublabel="Participant",
        layer=0, status=ComponentStatus.ACTIVE
    ))

    # Layer 1: Orchestration
    engine.add_node(ServiceNode(
        id="orchestrator", label="Orchestrator", sublabel="slate_orchestrator.py",
        layer=1, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="router", label="Task Router", sublabel="Workflow Dispatch",
        layer=1, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="scheduler", label="GPU Scheduler", sublabel="Load Balancing",
        layer=1, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(QueueNode(
        id="taskqueue", label="Task Queue", sublabel="current_tasks.json",
        layer=1, status=ComponentStatus.ACTIVE
    ))

    # Layer 2: Execution
    engine.add_node(ExternalNode(
        id="runner", label="GitHub Runner", sublabel="Self-Hosted",
        layer=2, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="multirunner", label="Multi-Runner", sublabel="Scales to Hardware",
        layer=2, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="actionguard", label="ActionGuard", sublabel="Security Layer",
        layer=2, status=ComponentStatus.ACTIVE
    ))

    # Layer 3: AI Backends
    engine.add_node(AINode(
        id="ollama", label="Ollama", sublabel=":11434 FREE",
        layer=3, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(AINode(
        id="foundry", label="Foundry Local", sublabel=":5272 ONNX",
        layer=3, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(DatabaseNode(
        id="chromadb", label="ChromaDB", sublabel="Vector Store",
        layer=3, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(GPUNode(
        id="gpu", label="Your GPU(s)", sublabel="Auto-Detected",
        layer=3, status=ComponentStatus.ACTIVE
    ))

    # Connections - UI to Orchestration
    engine.add_connector(FlowConnector(id="c1", from_node="dashboard", to_node="orchestrator"))
    engine.add_connector(FlowConnector(id="c2", from_node="cli", to_node="orchestrator"))
    engine.add_connector(FlowConnector(id="c3", from_node="vscode", to_node="orchestrator"))
    engine.add_connector(FlowConnector(id="c4", from_node="claude", to_node="orchestrator"))
    engine.add_connector(FlowConnector(id="c5", from_node="copilot", to_node="orchestrator"))

    # Orchestration connections
    engine.add_connector(FlowConnector(id="c6", from_node="orchestrator", to_node="router"))
    engine.add_connector(FlowConnector(id="c7", from_node="orchestrator", to_node="scheduler"))
    engine.add_connector(FlowConnector(id="c8", from_node="router", to_node="taskqueue"))

    # Execution connections
    engine.add_connector(FlowConnector(id="c9", from_node="router", to_node="runner"))
    engine.add_connector(FlowConnector(id="c10", from_node="scheduler", to_node="multirunner"))
    engine.add_connector(FlowConnector(id="c11", from_node="taskqueue", to_node="actionguard"))

    # AI Backend connections
    engine.add_connector(FlowConnector(id="c12", from_node="multirunner", to_node="ollama"))
    engine.add_connector(FlowConnector(id="c13", from_node="multirunner", to_node="foundry"))
    engine.add_connector(FlowConnector(id="c14", from_node="ollama", to_node="chromadb"))
    engine.add_connector(FlowConnector(id="c15", from_node="scheduler", to_node="gpu"))
    engine.add_connector(DashedConnector(id="c16", from_node="ollama", to_node="gpu"))
    engine.add_connector(DashedConnector(id="c17", from_node="foundry", to_node="gpu"))

    return engine.render_svg()


def generate_code_module_map() -> str:
    """Generate a map of the slate/ code modules."""
    config = SchematicConfig(
        title="SLATE Code Module Architecture",
        theme="blueprint",
        layout="hierarchical",
        width=1100,
        height=700,
        version_badge="v2.5",
        layer_spacing=120,
        node_spacing=85
    )
    engine = SchematicEngine(config)

    # Core Layer
    engine.add_node(ServiceNode(
        id="core", label="slate/__init__.py", sublabel="Core Package",
        layer=0, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="status", label="slate_status.py", sublabel="System Status",
        layer=0, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="runtime", label="slate_runtime.py", sublabel="Integrations",
        layer=0, status=ComponentStatus.ACTIVE
    ))

    # Orchestration Layer
    engine.add_node(ServiceNode(
        id="orch", label="slate_orchestrator.py", sublabel="Service Lifecycle",
        layer=1, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="workflow", label="slate_workflow_manager.py", sublabel="Task Lifecycle",
        layer=1, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="project", label="slate_project_board.py", sublabel="GitHub Projects",
        layer=1, status=ComponentStatus.ACTIVE
    ))

    # Execution Layer
    engine.add_node(ServiceNode(
        id="runner", label="slate_runner_manager.py", sublabel="Runner Setup",
        layer=2, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="multi", label="slate_multi_runner.py", sublabel="Parallel Exec",
        layer=2, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="benchmark", label="slate_runner_benchmark.py", sublabel="Capacity Test",
        layer=2, status=ComponentStatus.ACTIVE
    ))

    # AI Layer
    engine.add_node(AINode(
        id="unified", label="unified_ai_backend.py", sublabel="Central Router",
        layer=3, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(AINode(
        id="local", label="foundry_local.py", sublabel="Ollama + Foundry",
        layer=3, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="hardware", label="slate_hardware_optimizer.py", sublabel="GPU Detection",
        layer=3, status=ComponentStatus.ACTIVE
    ))

    # Security Layer
    engine.add_node(ServiceNode(
        id="guard", label="action_guard.py", sublabel="Action Validation",
        layer=4, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="sdk", label="sdk_source_guard.py", sublabel="Package Safety",
        layer=4, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="pii", label="pii_scanner.py", sublabel="Data Protection",
        layer=4, status=ComponentStatus.ACTIVE
    ))

    # Connections
    engine.add_connector(FlowConnector(id="m1", from_node="core", to_node="status"))
    engine.add_connector(FlowConnector(id="m2", from_node="core", to_node="runtime"))
    engine.add_connector(FlowConnector(id="m3", from_node="status", to_node="orch"))
    engine.add_connector(FlowConnector(id="m4", from_node="orch", to_node="workflow"))
    engine.add_connector(FlowConnector(id="m5", from_node="orch", to_node="project"))
    engine.add_connector(FlowConnector(id="m6", from_node="workflow", to_node="runner"))
    engine.add_connector(FlowConnector(id="m7", from_node="runner", to_node="multi"))
    engine.add_connector(FlowConnector(id="m8", from_node="multi", to_node="benchmark"))
    engine.add_connector(FlowConnector(id="m9", from_node="multi", to_node="unified"))
    engine.add_connector(FlowConnector(id="m10", from_node="unified", to_node="local"))
    engine.add_connector(FlowConnector(id="m11", from_node="unified", to_node="hardware"))
    engine.add_connector(DashedConnector(id="m12", from_node="runner", to_node="guard"))
    engine.add_connector(DashedConnector(id="m13", from_node="guard", to_node="sdk"))
    engine.add_connector(DashedConnector(id="m14", from_node="guard", to_node="pii"))

    return engine.render_svg()


def generate_ai_pipeline() -> str:
    """Generate the AI inference pipeline schematic."""
    config = SchematicConfig(
        title="SLATE AI Inference Pipeline",
        theme="blueprint",
        layout="hierarchical",
        width=1000,
        height=500,
        version_badge="v2.5",
        layer_spacing=130,
        node_spacing=100
    )
    engine = SchematicEngine(config)

    # Input Layer
    engine.add_node(ServiceNode(
        id="task", label="Task Input", sublabel="Code/Analysis/Docs",
        layer=0, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="context", label="Context", sublabel="RAG Memory",
        layer=0, status=ComponentStatus.ACTIVE
    ))

    # Routing Layer
    engine.add_node(ServiceNode(
        id="unified", label="Unified AI Backend", sublabel="Task Router",
        layer=1, status=ComponentStatus.ACTIVE
    ))

    # Backend Layer
    engine.add_node(AINode(
        id="ollama", label="Ollama", sublabel="mistral-nemo",
        layer=2, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(AINode(
        id="foundry", label="Foundry Local", sublabel="Phi-3/Mistral ONNX",
        layer=2, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ExternalNode(
        id="external", label="External APIs", sublabel="BLOCKED",
        layer=2, status=ComponentStatus.ERROR
    ))

    # Hardware Layer
    engine.add_node(GPUNode(
        id="gpu", label="GPU Compute", sublabel="Auto-Detected VRAM",
        layer=3, status=ComponentStatus.ACTIVE
    ))

    # Connections
    engine.add_connector(FlowConnector(id="a1", from_node="task", to_node="unified"))
    engine.add_connector(FlowConnector(id="a2", from_node="context", to_node="unified"))
    engine.add_connector(FlowConnector(id="a3", from_node="unified", to_node="ollama"))
    engine.add_connector(FlowConnector(id="a4", from_node="unified", to_node="foundry"))
    engine.add_connector(DashedConnector(id="a5", from_node="unified", to_node="external"))
    engine.add_connector(FlowConnector(id="a6", from_node="ollama", to_node="gpu"))
    engine.add_connector(FlowConnector(id="a7", from_node="foundry", to_node="gpu"))

    return engine.render_svg()


def generate_github_integration() -> str:
    """Generate the GitHub integration schematic."""
    config = SchematicConfig(
        title="SLATE GitHub Integration",
        theme="blueprint",
        layout="hierarchical",
        width=1000,
        height=550,
        version_badge="v2.5",
        layer_spacing=130,
        node_spacing=95
    )
    engine = SchematicEngine(config)

    # GitHub Cloud
    engine.add_node(ExternalNode(
        id="issues", label="GitHub Issues", sublabel="Task Source",
        layer=0, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ExternalNode(
        id="projects", label="Projects V2", sublabel="KANBAN Boards",
        layer=0, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ExternalNode(
        id="discussions", label="Discussions", sublabel="Community",
        layer=0, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ExternalNode(
        id="actions", label="GitHub Actions", sublabel="Workflows",
        layer=0, status=ComponentStatus.ACTIVE
    ))

    # Sync Layer
    engine.add_node(ServiceNode(
        id="sync", label="Bidirectional Sync", sublabel="Every 30min",
        layer=1, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="runner", label="Self-Hosted Runner", sublabel="GPU Labels",
        layer=1, status=ComponentStatus.ACTIVE
    ))

    # Local Processing
    engine.add_node(QueueNode(
        id="queue", label="Local Task Queue", sublabel="current_tasks.json",
        layer=2, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(AINode(
        id="ai", label="Local AI Processing", sublabel="Ollama/Foundry",
        layer=2, status=ComponentStatus.ACTIVE
    ))

    # Output
    engine.add_node(ServiceNode(
        id="output", label="Results", sublabel="PRs/Comments/Commits",
        layer=3, status=ComponentStatus.ACTIVE
    ))

    # Connections
    engine.add_connector(FlowConnector(id="g1", from_node="issues", to_node="sync"))
    engine.add_connector(FlowConnector(id="g2", from_node="projects", to_node="sync"))
    engine.add_connector(FlowConnector(id="g3", from_node="discussions", to_node="sync"))
    engine.add_connector(FlowConnector(id="g4", from_node="actions", to_node="runner"))
    engine.add_connector(FlowConnector(id="g5", from_node="sync", to_node="queue"))
    engine.add_connector(FlowConnector(id="g6", from_node="runner", to_node="queue"))
    engine.add_connector(FlowConnector(id="g7", from_node="queue", to_node="ai"))
    engine.add_connector(FlowConnector(id="g8", from_node="ai", to_node="output"))
    engine.add_connector(DashedConnector(id="g9", from_node="output", to_node="issues"))
    engine.add_connector(DashedConnector(id="g10", from_node="output", to_node="projects"))

    return engine.render_svg()


def generate_multi_runner_system() -> str:
    """Generate the multi-runner system schematic."""
    config = SchematicConfig(
        title="SLATE Multi-Runner System",
        theme="blueprint",
        layout="hierarchical",
        width=950,
        height=550,
        version_badge="v2.5",
        layer_spacing=130,
        node_spacing=90
    )
    engine = SchematicEngine(config)

    # Task Input
    engine.add_node(QueueNode(
        id="tasks", label="Task Queue", sublabel="Pending Work",
        layer=0, status=ComponentStatus.ACTIVE
    ))

    # Scheduler
    engine.add_node(ServiceNode(
        id="scheduler", label="Resource Scheduler", sublabel="VRAM + Core Aware",
        layer=1, status=ComponentStatus.ACTIVE
    ))

    # GPU Runners
    engine.add_node(GPUNode(
        id="heavy", label="GPU Heavy", sublabel="Large Inference",
        layer=2, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(GPUNode(
        id="light1", label="GPU Light", sublabel="Quick Tasks",
        layer=2, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(GPUNode(
        id="light2", label="GPU Light", sublabel="Quick Tasks",
        layer=2, status=ComponentStatus.ACTIVE
    ))

    # CPU Runners
    engine.add_node(ServiceNode(
        id="cpu1", label="CPU Runner", sublabel="Lint/Test",
        layer=3, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="cpu2", label="CPU Runner", sublabel="Git Ops",
        layer=3, status=ComponentStatus.ACTIVE
    ))
    engine.add_node(ServiceNode(
        id="cpu3", label="CPU Runner", sublabel="File Ops",
        layer=3, status=ComponentStatus.ACTIVE
    ))

    # Connections
    engine.add_connector(FlowConnector(id="r1", from_node="tasks", to_node="scheduler"))
    engine.add_connector(FlowConnector(id="r2", from_node="scheduler", to_node="heavy"))
    engine.add_connector(FlowConnector(id="r3", from_node="scheduler", to_node="light1"))
    engine.add_connector(FlowConnector(id="r4", from_node="scheduler", to_node="light2"))
    engine.add_connector(FlowConnector(id="r5", from_node="scheduler", to_node="cpu1"))
    engine.add_connector(FlowConnector(id="r6", from_node="scheduler", to_node="cpu2"))
    engine.add_connector(FlowConnector(id="r7", from_node="scheduler", to_node="cpu3"))

    # Add annotation
    engine.add_annotation(Annotation(
        id="note1",
        text="Runner count scales to YOUR hardware",
        position=(475, 500),
        style="note",
        anchor="middle"
    ))

    return engine.render_svg()


def main():
    """Generate all schematics and save to docs/assets/."""
    output_dir = WORKSPACE_ROOT / "docs" / "assets" / "schematics"
    output_dir.mkdir(parents=True, exist_ok=True)

    schematics = [
        ("system-architecture-full", generate_complete_architecture),
        ("code-module-map", generate_code_module_map),
        ("ai-inference-pipeline", generate_ai_pipeline),
        ("github-integration", generate_github_integration),
        ("multi-runner-system", generate_multi_runner_system),
    ]

    print("Generating SLATE website schematics...")
    for name, generator in schematics:
        try:
            svg_content = generator()
            output_path = output_dir / f"{name}.svg"
            output_path.write_text(svg_content, encoding="utf-8")
            print(f"  [OK] {name}.svg")
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")

    # Also copy to pages directory for direct web access
    pages_assets = WORKSPACE_ROOT / "docs" / "pages" / "assets" / "schematics"
    pages_assets.mkdir(parents=True, exist_ok=True)
    for name, _ in schematics:
        src = output_dir / f"{name}.svg"
        dst = pages_assets / f"{name}.svg"
        if src.exists():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"\nGenerated {len(schematics)} schematics to:")
    print(f"  - {output_dir}")
    print(f"  - {pages_assets}")


if __name__ == "__main__":
    main()
