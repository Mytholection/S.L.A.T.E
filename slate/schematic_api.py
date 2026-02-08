#!/usr/bin/env python3
# Modified: 2026-02-08T02:00:00Z | Author: Claude Opus 4.5 | Change: Create schematic dashboard API
"""
SLATE Schematic API - Dashboard Integration

Provides FastAPI routes for schematic diagram generation and real-time
visualization in the SLATE dashboard. Part of Generative UI protocols.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

# Add workspace root for imports
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from slate.schematic_sdk import (
    SchematicEngine,
    SchematicConfig,
    ComponentStatus,
    ServiceNode,
    AINode,
    GPUNode,
    DatabaseNode,
    FlowConnector,
    DashedConnector,
    generate_from_system_state,
    generate_from_tech_tree,
)
from slate.schematic_sdk.library import (
    TEMPLATES,
    list_templates,
    build_from_template,
    slate_dashboard,
    slate_ollama,
    slate_foundry,
    slate_chromadb,
    slate_dual_gpu,
    slate_runner,
)
from slate.schematic_sdk.exporters import (
    Base64Exporter,
    HTMLExporter,
    JSONExporter,
)

router = APIRouter(prefix="/api/schematic", tags=["schematic"])


# ── Request/Response Models ──────────────────────────────────────────────────

class TemplateListResponse(BaseModel):
    """Response for template listing."""
    templates: List[Dict[str, str]]


class SchematicResponse(BaseModel):
    """Response containing SVG schematic."""
    svg: str
    title: str
    width: int
    height: int
    format: str = "svg"


class SchematicBase64Response(BaseModel):
    """Response with base64-encoded schematic."""
    data_uri: str
    img_tag: str
    title: str


class CustomSchematicRequest(BaseModel):
    """Request for custom schematic generation."""
    title: str = "Custom Schematic"
    width: int = 900
    height: int = 600
    theme: str = "blueprint"
    layout: str = "hierarchical"
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    connections: List[Dict[str, Any]] = Field(default_factory=list)


class LiveStatusRequest(BaseModel):
    """Request for live status schematic."""
    services: Dict[str, str] = Field(default_factory=dict)  # service_id -> status


# ── Template Endpoints ───────────────────────────────────────────────────────

@router.get("/templates", response_model=TemplateListResponse)
async def get_templates() -> TemplateListResponse:
    """
    List available schematic templates.

    Returns:
        List of template IDs with names and descriptions.
    """
    return TemplateListResponse(templates=list_templates())


@router.get("/template/{template_id}")
async def render_template(
    template_id: str,
    format: str = "svg",
) -> Dict[str, Any]:
    """
    Render a pre-built schematic template.

    Args:
        template_id: Template identifier (system, inference, cicd)
        format: Output format (svg, base64, json)

    Returns:
        Schematic in requested format
    """
    if template_id not in TEMPLATES:
        raise HTTPException(
            status_code=404,
            detail=f"Template not found: {template_id}. Available: {', '.join(TEMPLATES.keys())}",
        )

    try:
        svg = build_from_template(template_id)
        template = TEMPLATES[template_id]
        config = template["config"]

        if format == "base64":
            return {
                "data_uri": Base64Exporter.encode(svg),
                "img_tag": Base64Exporter.to_img_tag(svg, alt=config.title),
                "title": config.title,
            }
        elif format == "json":
            return json.loads(JSONExporter.to_manifest(svg, metadata={
                "template_id": template_id,
                "title": config.title,
            }))
        else:
            return {
                "svg": svg,
                "title": config.title,
                "width": config.width,
                "height": config.height,
                "format": "svg",
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── System State Endpoints ───────────────────────────────────────────────────

@router.get("/system-state")
async def get_system_state_schematic(
    format: str = "svg",
) -> Dict[str, Any]:
    """
    Generate schematic from current SLATE system state.

    Args:
        format: Output format (svg, base64, json)

    Returns:
        Live system architecture diagram
    """
    try:
        svg = generate_from_system_state()

        if format == "base64":
            return {
                "data_uri": Base64Exporter.encode(svg),
                "img_tag": Base64Exporter.to_img_tag(svg, alt="SLATE System Architecture"),
                "title": "SLATE System Architecture",
            }
        elif format == "json":
            return json.loads(JSONExporter.to_manifest(svg, metadata={
                "type": "system-state",
            }))
        else:
            return {
                "svg": svg,
                "title": "SLATE System Architecture",
                "width": 900,
                "height": 600,
                "format": "svg",
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tech-tree")
async def get_tech_tree_schematic(
    format: str = "svg",
) -> Dict[str, Any]:
    """
    Generate schematic from SLATE tech tree.

    Args:
        format: Output format (svg, base64, json)

    Returns:
        Tech tree visualization as schematic
    """
    try:
        svg = generate_from_tech_tree()

        if format == "base64":
            return {
                "data_uri": Base64Exporter.encode(svg),
                "img_tag": Base64Exporter.to_img_tag(svg, alt="SLATE Tech Tree"),
                "title": "SLATE Tech Tree",
            }
        else:
            return {
                "svg": svg,
                "title": "SLATE Tech Tree",
                "width": 1000,
                "height": 700,
                "format": "svg",
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/live-status")
async def get_live_status_schematic(
    request: LiveStatusRequest,
) -> Dict[str, Any]:
    """
    Generate schematic with live service status.

    Args:
        request: Service status mappings

    Returns:
        Schematic with status-colored nodes
    """
    status_map = {
        "active": ComponentStatus.ACTIVE,
        "pending": ComponentStatus.PENDING,
        "error": ComponentStatus.ERROR,
        "inactive": ComponentStatus.INACTIVE,
    }

    config = SchematicConfig(
        title="SLATE Live Status",
        theme="blueprint",
        layout="hierarchical",
        width=900,
        height=500,
    )
    engine = SchematicEngine(config)

    # Map service statuses
    services = request.services or {}

    # Add core components with status
    engine.add_node(slate_dashboard(status_map.get(services.get("dashboard", "active"), ComponentStatus.ACTIVE)))
    engine.add_node(slate_ollama(status_map.get(services.get("ollama", "active"), ComponentStatus.ACTIVE)))
    engine.add_node(slate_foundry(status_map.get(services.get("foundry", "inactive"), ComponentStatus.INACTIVE)))
    engine.add_node(slate_chromadb(status_map.get(services.get("chromadb", "active"), ComponentStatus.ACTIVE)))
    engine.add_node(slate_dual_gpu(status_map.get(services.get("gpu", "active"), ComponentStatus.ACTIVE)))
    engine.add_node(slate_runner(status_map.get(services.get("runner", "active"), ComponentStatus.ACTIVE)))

    # Add connections
    engine.add_connector(FlowConnector(id="c1", from_node="dashboard", to_node="ollama", label="API"))
    engine.add_connector(FlowConnector(id="c2", from_node="dashboard", to_node="runner"))
    engine.add_connector(FlowConnector(id="c3", from_node="ollama", to_node="gpu-cluster", label="CUDA"))
    engine.add_connector(DashedConnector(id="c4", from_node="ollama", to_node="chromadb", label="RAG"))

    svg = engine.render_svg()

    return {
        "svg": svg,
        "title": "SLATE Live Status",
        "width": 900,
        "height": 500,
        "format": "svg",
        "services": services,
    }


# ── Custom Schematic Endpoints ───────────────────────────────────────────────

@router.post("/custom")
async def create_custom_schematic(
    request: CustomSchematicRequest,
) -> Dict[str, Any]:
    """
    Create a custom schematic from node/connection definitions.

    Args:
        request: Custom schematic definition

    Returns:
        Generated SVG schematic
    """
    config = SchematicConfig(
        title=request.title,
        theme=request.theme,
        layout=request.layout,
        width=request.width,
        height=request.height,
    )
    engine = SchematicEngine(config)

    # Process nodes
    node_type_map = {
        "service": ServiceNode,
        "ai": AINode,
        "gpu": GPUNode,
        "database": DatabaseNode,
    }

    for node_def in request.nodes:
        node_type = node_def.pop("type", "service")
        node_class = node_type_map.get(node_type, ServiceNode)

        # Convert status string to enum
        if "status" in node_def:
            status_str = node_def.pop("status")
            node_def["status"] = ComponentStatus(status_str)

        engine.add_node(node_class(**node_def))

    # Process connections
    for conn_def in request.connections:
        engine.add_connector(FlowConnector(**conn_def))

    svg = engine.render_svg()

    return {
        "svg": svg,
        "title": request.title,
        "width": request.width,
        "height": request.height,
        "format": "svg",
    }


# ── Embeddable Widget Endpoints ──────────────────────────────────────────────

@router.get("/widget/system")
async def get_system_widget() -> Dict[str, Any]:
    """
    Get embeddable system architecture widget for dashboard.

    Returns:
        HTML-ready schematic widget
    """
    svg = generate_from_system_state()

    return {
        "html": f'''<div class="schematic-widget" data-type="system-architecture">
            <div class="schematic-header">
                <span class="schematic-title">System Architecture</span>
                <span class="schematic-status" data-live="true">Live</span>
            </div>
            <div class="schematic-content">
                {svg}
            </div>
        </div>''',
        "css": get_widget_css(),
        "js": get_widget_js(),
    }


@router.get("/widget/compact")
async def get_compact_widget(
    template_id: str = "system",
) -> Dict[str, Any]:
    """
    Get compact schematic widget for sidebar/control panel.

    Args:
        template_id: Template to render

    Returns:
        Compact widget HTML
    """
    if template_id not in TEMPLATES:
        template_id = "system"

    svg = build_from_template(template_id)
    template = TEMPLATES[template_id]

    # Create compact version by wrapping with viewBox scaling
    compact_svg = svg.replace(
        f'width="{template["config"].width}"',
        'width="100%"'
    ).replace(
        f'height="{template["config"].height}"',
        'height="auto"'
    )

    return {
        "html": f'''<div class="schematic-compact" data-template="{template_id}">
            {compact_svg}
        </div>''',
        "template": template_id,
        "title": template["name"],
    }


# ── WebSocket for Live Updates ───────────────────────────────────────────────

class SchematicWebSocketManager:
    """Manage WebSocket connections for live schematic updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


ws_manager = SchematicWebSocketManager()


@router.websocket("/ws/live")
async def schematic_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for live schematic updates.

    Broadcasts schematic updates when system state changes.
    """
    await ws_manager.connect(websocket)
    try:
        # Send initial schematic
        svg = generate_from_system_state()
        await websocket.send_json({
            "type": "schematic_update",
            "svg": svg,
            "title": "SLATE System Architecture",
        })

        # Listen for client messages (status requests, etc.)
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "request_update":
                svg = generate_from_system_state()
                await websocket.send_json({
                    "type": "schematic_update",
                    "svg": svg,
                    "timestamp": data.get("timestamp"),
                })

            elif data.get("type") == "request_template":
                template_id = data.get("template_id", "system")
                if template_id in TEMPLATES:
                    svg = build_from_template(template_id)
                    await websocket.send_json({
                        "type": "template_update",
                        "template_id": template_id,
                        "svg": svg,
                    })

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


async def broadcast_schematic_update(svg: str, title: str = "SLATE System"):
    """Broadcast schematic update to all connected clients."""
    await ws_manager.broadcast({
        "type": "schematic_update",
        "svg": svg,
        "title": title,
    })


# ── Helper Functions ─────────────────────────────────────────────────────────

def get_widget_css() -> str:
    """Get CSS for schematic widgets."""
    return """
.schematic-widget {
    background: #1A1816;
    border: 1px solid #3A3634;
    border-radius: 12px;
    overflow: hidden;
}

.schematic-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: #2A2624;
    border-bottom: 1px solid #3A3634;
}

.schematic-title {
    font-family: 'Segoe UI', sans-serif;
    font-weight: 600;
    color: #E8E2DE;
    font-size: 14px;
}

.schematic-status {
    font-family: 'Consolas', monospace;
    font-size: 10px;
    padding: 2px 8px;
    background: rgba(34, 197, 94, 0.15);
    color: #22C55E;
    border-radius: 4px;
}

.schematic-status::before {
    content: '';
    display: inline-block;
    width: 6px;
    height: 6px;
    background: #22C55E;
    border-radius: 50%;
    margin-right: 6px;
    animation: pulse 2s infinite;
}

.schematic-content {
    padding: 16px;
}

.schematic-content svg {
    width: 100%;
    height: auto;
    display: block;
}

.schematic-compact {
    background: #1A1816;
    border: 1px solid #3A3634;
    border-radius: 8px;
    padding: 8px;
}

.schematic-compact svg {
    width: 100%;
    height: auto;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
"""


def get_widget_js() -> str:
    """Get JavaScript for schematic widget interactivity."""
    return """
class SchematicWidget {
    constructor(container) {
        this.container = container;
        this.ws = null;
        this.connectWebSocket();
    }

    connectWebSocket() {
        this.ws = new WebSocket(`ws://${window.location.host}/api/schematic/ws/live`);

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'schematic_update') {
                this.updateSchematic(data.svg);
            }
        };

        this.ws.onclose = () => {
            setTimeout(() => this.connectWebSocket(), 5000);
        };
    }

    updateSchematic(svg) {
        const content = this.container.querySelector('.schematic-content');
        if (content) {
            content.innerHTML = svg;
        }
    }

    requestUpdate() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'request_update',
                timestamp: Date.now()
            }));
        }
    }
}

// Auto-initialize widgets
document.querySelectorAll('.schematic-widget[data-live="true"]').forEach(el => {
    new SchematicWidget(el);
});
"""
