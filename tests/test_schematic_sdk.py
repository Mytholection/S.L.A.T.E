#!/usr/bin/env python3
# Modified: 2026-02-08T01:20:00Z | Author: COPILOT | Change: Create comprehensive tests for schematic SDK
"""
Tests for SLATE Schematic Diagram Generation SDK.

Covers: components, theme, layout, SVG renderer, engine, library, exporters.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure workspace root on path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from slate.schematic_sdk.components import (
    Annotation,
    APINode,
    Component,
    ComponentStatus,
    ComponentType,
    Connection,
    ConnectionStyle,
    DatabaseNode,
    DataBus,
    DashedConnector,
    ExternalNode,
    FlowConnector,
    GPUNode,
    AINode,
    Layer,
    Port,
    PortPosition,
    QueueNode,
    SchematicConfig,
    ServiceNode,
    InputTerminal,
    OutputTerminal,
)
from slate.schematic_sdk.theme import (
    BlueprintTheme,
    DarkTheme,
    LightTheme,
    SchematicColors,
    SchematicEffects,
    SchematicTheme,
    SchematicTypography,
    ThemeManager,
)
from slate.schematic_sdk.layout import (
    ForceDirectedLayout,
    GridLayout,
    HierarchicalLayout,
    LayoutEngine,
    LayoutResult,
    get_layout_engine,
)
from slate.schematic_sdk.svg_renderer import SVGRenderer
from slate.schematic_sdk.engine import (
    SchematicEngine,
    generate_from_system_state,
    generate_system_diagram,
)
from slate.schematic_sdk.library import (
    TEMPLATES,
    build_from_template,
    get_ai_inference_template,
    get_cicd_pipeline_template,
    get_slate_system_template,
    list_templates,
    slate_chromadb,
    slate_dashboard,
    slate_dual_gpu,
    slate_gpu,
    slate_ollama,
    slate_runner,
    slate_vscode,
)
from slate.schematic_sdk.exporters import (
    Base64Exporter,
    HTMLExporter,
    JSONExporter,
    MarkdownExporter,
    SVGExporter,
)


# ── Component Tests ──────────────────────────────────────────────────────────

class TestComponentEnums:
    """Test component enumerations."""

    def test_component_types(self):
        assert ComponentType.SERVICE == "service"
        assert ComponentType.DATABASE == "database"
        assert ComponentType.GPU == "gpu"
        assert ComponentType.AI == "ai"
        assert ComponentType.API == "api"
        assert ComponentType.QUEUE == "queue"
        assert ComponentType.EXTERNAL == "external"

    def test_connection_styles(self):
        assert ConnectionStyle.SOLID == "solid"
        assert ConnectionStyle.DASHED == "dashed"
        assert ConnectionStyle.DOTTED == "dotted"

    def test_component_status(self):
        assert ComponentStatus.ACTIVE == "active"
        assert ComponentStatus.PENDING == "pending"
        assert ComponentStatus.ERROR == "error"
        assert ComponentStatus.INACTIVE == "inactive"

    def test_port_positions(self):
        assert PortPosition.TOP == "top"
        assert PortPosition.RIGHT == "right"
        assert PortPosition.BOTTOM == "bottom"
        assert PortPosition.LEFT == "left"


class TestPort:
    """Test Port dataclass."""

    def test_default_port(self):
        p = Port(id="p1")
        assert p.id == "p1"
        assert p.position == PortPosition.RIGHT
        assert p.type == "bidirectional"

    def test_custom_port(self):
        p = Port(id="p2", position=PortPosition.TOP, type="input")
        assert p.position == PortPosition.TOP
        assert p.type == "input"


class TestComponent:
    """Test base Component and all node types."""

    def test_base_component(self):
        c = Component(id="test", type=ComponentType.SERVICE, label="Test")
        assert c.id == "test"
        assert c.label == "Test"
        assert c.status == ComponentStatus.ACTIVE
        assert len(c.ports) == 2  # Default left+right

    def test_service_node(self):
        n = ServiceNode(id="svc", label="My Service", sublabel=":8080")
        assert n.type == ComponentType.SERVICE
        assert n.shape == "rounded_rect"
        assert n.size == (140, 60)
        assert n.sublabel == ":8080"

    def test_database_node(self):
        n = DatabaseNode(id="db", label="PostgreSQL")
        assert n.type == ComponentType.DATABASE
        assert n.shape == "cylinder"
        assert n.size == (100, 80)

    def test_gpu_node(self):
        n = GPUNode(id="gpu0", label="GPU 0", sublabel="RTX 5070 Ti")
        assert n.type == ComponentType.GPU
        assert n.shape == "hexagon"
        assert n.size == (120, 80)

    def test_ai_node(self):
        n = AINode(id="ollama", label="Ollama", sublabel=":11434")
        assert n.type == ComponentType.AI
        assert n.shape == "ai_node"

    def test_api_node(self):
        n = APINode(id="api", label="REST API", port_number=8080)
        assert n.type == ComponentType.API
        assert n.port_number == 8080

    def test_queue_node(self):
        n = QueueNode(id="q", label="Task Queue")
        assert n.type == ComponentType.QUEUE
        assert n.shape == "parallelogram"

    def test_external_node(self):
        n = ExternalNode(id="ext", label="GitHub")
        assert n.type == ComponentType.EXTERNAL
        assert n.shape == "external"

    def test_custom_size(self):
        n = ServiceNode(id="big", label="Large", size=(200, 100))
        assert n.size == (200, 100)

    def test_custom_status(self):
        n = ServiceNode(id="err", label="Error", status=ComponentStatus.ERROR)
        assert n.status == ComponentStatus.ERROR

    def test_layer_assignment(self):
        n = ServiceNode(id="l2", label="Layer 2", layer=2)
        assert n.layer == 2


class TestConnection:
    """Test Connection and connector types."""

    def test_base_connection(self):
        c = Connection(id="c1", from_node="a", to_node="b")
        assert c.style == ConnectionStyle.SOLID
        assert c.animated is False
        assert c.bidirectional is False

    def test_flow_connector(self):
        c = FlowConnector(id="f1", from_node="a", to_node="b", label="Data")
        assert c.style == ConnectionStyle.SOLID
        assert c.label == "Data"

    def test_dashed_connector(self):
        c = DashedConnector(id="d1", from_node="a", to_node="b")
        assert c.style == ConnectionStyle.DASHED

    def test_data_bus(self):
        b = DataBus(id="bus1", from_node="a", to_node="b", connected_nodes=["c", "d"])
        assert len(b.connected_nodes) == 2
        assert b.bus_width == 4.0


class TestTerminals:
    """Test terminal components."""

    def test_input_terminal(self):
        t = InputTerminal(id="in1", label="Requests")
        assert t.label == "Requests"
        assert t.connected_to is None

    def test_output_terminal(self):
        t = OutputTerminal(id="out1", label="Responses", connected_from="api")
        assert t.connected_from == "api"


class TestAnnotation:
    """Test Annotation dataclass."""

    def test_default_annotation(self):
        a = Annotation(id="a1", text="Note", position=(100, 200))
        assert a.style == "label"
        assert a.anchor == "start"

    def test_title_annotation(self):
        a = Annotation(id="a2", text="Title", position=(50, 50), style="title", anchor="middle")
        assert a.style == "title"


class TestSchematicConfig:
    """Test SchematicConfig dataclass."""

    def test_defaults(self):
        c = SchematicConfig()
        assert c.width == 900
        assert c.height == 600
        assert c.theme == "blueprint"
        assert c.layout == "hierarchical"
        assert c.show_grid is True
        assert c.show_legend is True
        assert c.show_title is True
        assert c.padding == 40

    def test_custom_config(self):
        c = SchematicConfig(width=1200, height=800, title="Custom", theme="dark")
        assert c.width == 1200
        assert c.title == "Custom"
        assert c.theme == "dark"


# ── Theme Tests ──────────────────────────────────────────────────────────────

class TestThemeManager:
    """Test ThemeManager and themes."""

    def test_blueprint_theme(self):
        tm = ThemeManager("blueprint")
        assert tm.theme is not None
        assert tm.theme.colors.background == "#0D1B2A"

    def test_dark_theme(self):
        tm = ThemeManager("dark")
        assert tm.theme is not None

    def test_light_theme(self):
        tm = ThemeManager("light")
        assert tm.theme is not None

    def test_status_colors(self):
        tm = ThemeManager("blueprint")
        active = tm.get_status_color("active")
        assert active.startswith("#")
        error = tm.get_status_color("error")
        assert error.startswith("#")

    def test_component_fill(self):
        tm = ThemeManager("blueprint")
        fill = tm.get_component_fill("service")
        assert isinstance(fill, str)

    def test_component_border(self):
        tm = ThemeManager("blueprint")
        border = tm.get_component_border("gpu", "active")
        assert isinstance(border, str)


class TestSchematicColors:
    """Test SchematicColors dataclass."""

    def test_has_required_fields(self):
        c = SchematicColors()
        assert hasattr(c, "background")
        assert hasattr(c, "primary")
        assert hasattr(c, "status_active")
        assert hasattr(c, "status_error")
        assert hasattr(c, "grid_lines")


class TestSchematicTypography:
    """Test SchematicTypography dataclass."""

    def test_has_fonts(self):
        t = SchematicTypography()
        assert hasattr(t, "font_display")
        assert hasattr(t, "font_mono")
        assert hasattr(t, "label_size")


# ── Layout Tests ─────────────────────────────────────────────────────────────

class TestLayoutResult:
    """Test LayoutResult dataclass."""

    def test_layout_result(self):
        r = LayoutResult(positions={"a": (100, 200), "b": (300, 400)}, bounds=(0, 0, 500, 500))
        assert r.positions["a"] == (100, 200)
        assert len(r.positions) == 2
        assert r.bounds == (0, 0, 500, 500)


class TestHierarchicalLayout:
    """Test HierarchicalLayout algorithm."""

    def test_basic_layout(self):
        layout = HierarchicalLayout()
        comps = [
            ServiceNode(id="a", label="A", layer=0),
            ServiceNode(id="b", label="B", layer=1),
        ]
        conns = [FlowConnector(id="c1", from_node="a", to_node="b")]
        config = SchematicConfig()
        result = layout.calculate_positions(comps, conns, config)
        assert "a" in result.positions
        assert "b" in result.positions
        # Layer 0 should be above layer 1
        assert result.positions["a"][1] < result.positions["b"][1]

    def test_multiple_same_layer(self):
        layout = HierarchicalLayout()
        comps = [
            ServiceNode(id="a", label="A", layer=0),
            ServiceNode(id="b", label="B", layer=0),
            ServiceNode(id="c", label="C", layer=1),
        ]
        conns = []
        config = SchematicConfig()
        result = layout.calculate_positions(comps, conns, config)
        assert len(result.positions) == 3
        # Same layer nodes should have same Y but different X
        assert result.positions["a"][1] == result.positions["b"][1]
        assert result.positions["a"][0] != result.positions["b"][0]


class TestForceDirectedLayout:
    """Test ForceDirectedLayout algorithm."""

    def test_basic_layout(self):
        layout = ForceDirectedLayout(iterations=10)
        comps = [
            ServiceNode(id="a", label="A"),
            ServiceNode(id="b", label="B"),
        ]
        conns = [FlowConnector(id="c1", from_node="a", to_node="b")]
        config = SchematicConfig()
        result = layout.calculate_positions(comps, conns, config)
        assert "a" in result.positions
        assert "b" in result.positions

    def test_nodes_spread(self):
        """Nodes should not overlap after force-directed layout."""
        layout = ForceDirectedLayout(iterations=50)
        comps = [
            ServiceNode(id="a", label="A"),
            ServiceNode(id="b", label="B"),
            ServiceNode(id="c", label="C"),
        ]
        conns = [
            FlowConnector(id="c1", from_node="a", to_node="b"),
            FlowConnector(id="c2", from_node="b", to_node="c"),
        ]
        config = SchematicConfig()
        result = layout.calculate_positions(comps, conns, config)
        # All three should have distinct positions
        positions = list(result.positions.values())
        assert positions[0] != positions[1]
        assert positions[1] != positions[2]


class TestGridLayout:
    """Test GridLayout algorithm."""

    def test_basic_grid(self):
        layout = GridLayout(columns=2)
        comps = [
            ServiceNode(id="a", label="A"),
            ServiceNode(id="b", label="B"),
            ServiceNode(id="c", label="C"),
            ServiceNode(id="d", label="D"),
        ]
        config = SchematicConfig()
        result = layout.calculate_positions(comps, [], config)
        assert len(result.positions) == 4

    def test_grid_alignment(self):
        layout = GridLayout(columns=3)
        comps = [ServiceNode(id=f"n{i}", label=f"N{i}") for i in range(6)]
        config = SchematicConfig()
        result = layout.calculate_positions(comps, [], config)
        # First row (n0, n1, n2) should have same Y
        assert result.positions["n0"][1] == result.positions["n1"][1]
        assert result.positions["n1"][1] == result.positions["n2"][1]
        # Second row should be different Y
        assert result.positions["n3"][1] > result.positions["n0"][1]


class TestGetLayoutEngine:
    """Test layout engine factory."""

    def test_hierarchical(self):
        engine = get_layout_engine("hierarchical")
        assert isinstance(engine, HierarchicalLayout)

    def test_force(self):
        engine = get_layout_engine("force")
        assert isinstance(engine, ForceDirectedLayout)

    def test_grid(self):
        engine = get_layout_engine("grid")
        assert isinstance(engine, GridLayout)


# ── SVG Renderer Tests ───────────────────────────────────────────────────────

class TestSVGRenderer:
    """Test SVG rendering."""

    def _make_renderer(self):
        return SVGRenderer(ThemeManager("blueprint"))

    def test_render_empty(self):
        r = self._make_renderer()
        svg = r.render([], [], {}, SchematicConfig())
        assert svg.startswith("<?xml")
        assert "</svg>" in svg
        assert "viewBox" in svg

    def test_render_with_components(self):
        r = self._make_renderer()
        comps = [ServiceNode(id="svc", label="Service", sublabel=":8080")]
        positions = {"svc": (450, 300)}
        config = SchematicConfig()
        svg = r.render(comps, [], positions, config)
        assert "Service" in svg
        assert ":8080" in svg
        assert 'data-id="svc"' in svg

    def test_render_database_shape(self):
        r = self._make_renderer()
        comps = [DatabaseNode(id="db", label="DB")]
        positions = {"db": (200, 200)}
        svg = r.render(comps, [], positions, SchematicConfig())
        assert 'data-type="database"' in svg
        assert "ellipse" in svg  # Cylinder has ellipse top

    def test_render_gpu_shape(self):
        r = self._make_renderer()
        comps = [GPUNode(id="g", label="GPU")]
        positions = {"g": (200, 200)}
        svg = r.render(comps, [], positions, SchematicConfig())
        assert 'data-type="gpu"' in svg
        assert "polygon" in svg  # Hexagon uses polygon

    def test_render_queue_shape(self):
        r = self._make_renderer()
        comps = [QueueNode(id="q", label="Queue")]
        positions = {"q": (200, 200)}
        svg = r.render(comps, [], positions, SchematicConfig())
        assert 'data-type="queue"' in svg

    def test_render_connections(self):
        r = self._make_renderer()
        comps = [
            ServiceNode(id="a", label="A"),
            ServiceNode(id="b", label="B"),
        ]
        conns = [FlowConnector(id="c1", from_node="a", to_node="b", label="Flow")]
        positions = {"a": (200, 300), "b": (600, 300)}
        svg = r.render(comps, conns, positions, SchematicConfig())
        assert "Flow" in svg
        assert 'data-from="a"' in svg
        assert 'data-to="b"' in svg

    def test_render_grid(self):
        r = self._make_renderer()
        svg = r.render([], [], {}, SchematicConfig(show_grid=True))
        assert "gridPattern" in svg

    def test_render_no_grid(self):
        r = self._make_renderer()
        svg = r.render([], [], {}, SchematicConfig(show_grid=False))
        assert "Grid Overlay" not in svg

    def test_render_legend(self):
        r = self._make_renderer()
        svg = r.render([], [], {}, SchematicConfig(show_legend=True))
        assert "legend" in svg.lower()
        assert "Active" in svg

    def test_render_version_badge(self):
        r = self._make_renderer()
        svg = r.render([], [], {}, SchematicConfig(version_badge="v2.5"))
        assert "v2.5" in svg

    def test_render_title(self):
        r = self._make_renderer()
        svg = r.render([], [], {}, SchematicConfig(title="My Title", show_title=True))
        assert "My Title" in svg

    def test_defs_present(self):
        r = self._make_renderer()
        svg = r.render([], [], {}, SchematicConfig())
        assert "<defs>" in svg
        assert "bgGradient" in svg
        assert "arrowhead" in svg
        assert "shadow" in svg


# ── Engine Tests ─────────────────────────────────────────────────────────────

class TestSchematicEngine:
    """Test SchematicEngine orchestrator."""

    def test_create_default(self):
        e = SchematicEngine()
        assert e.config.width == 900
        assert len(e.components) == 0

    def test_create_with_config(self):
        c = SchematicConfig(title="Test", width=1200)
        e = SchematicEngine(c)
        assert e.config.title == "Test"
        assert e.config.width == 1200

    def test_add_node(self):
        e = SchematicEngine()
        result = e.add_node(ServiceNode(id="s", label="S"))
        assert len(e.components) == 1
        assert result is e  # Fluent API

    def test_add_connector(self):
        e = SchematicEngine()
        result = e.add_connector(FlowConnector(id="c", from_node="a", to_node="b"))
        assert len(e.connections) == 1
        assert result is e

    def test_add_annotation(self):
        e = SchematicEngine()
        result = e.add_annotation(Annotation(id="a", text="Note", position=(50, 50)))
        assert len(e.annotations) == 1
        assert result is e

    def test_fluent_api(self):
        svg = (
            SchematicEngine(SchematicConfig(title="Fluent"))
            .add_node(ServiceNode(id="a", label="A"))
            .add_node(ServiceNode(id="b", label="B"))
            .add_connector(FlowConnector(id="c", from_node="a", to_node="b"))
            .render_svg()
        )
        assert "<?xml" in svg
        assert "</svg>" in svg

    def test_render_svg(self):
        e = SchematicEngine()
        e.add_node(ServiceNode(id="api", label="API"))
        svg = e.render_svg()
        assert "API" in svg
        assert "viewBox" in svg

    def test_auto_layout_on_render(self):
        """Engine should auto-apply layout if not done explicitly."""
        e = SchematicEngine()
        e.add_node(ServiceNode(id="a", label="A"))
        e.add_node(ServiceNode(id="b", label="B"))
        svg = e.render_svg()
        assert len(e.positions) == 2

    def test_set_theme(self):
        e = SchematicEngine()
        result = e.set_theme("dark")
        assert result is e

    def test_set_layout(self):
        e = SchematicEngine()
        result = e.set_layout("grid")
        assert result is e

    def test_to_dict(self):
        e = SchematicEngine()
        e.add_node(ServiceNode(id="s", label="S"))
        d = e.to_dict()
        assert "config" in d
        assert "components" in d
        assert len(d["components"]) == 1

    def test_to_json(self):
        e = SchematicEngine()
        e.add_node(ServiceNode(id="s", label="S"))
        j = e.to_json()
        data = json.loads(j)
        assert data["config"]["width"] == 900

    def test_save_svg(self):
        e = SchematicEngine()
        e.add_node(ServiceNode(id="s", label="Save Test"))
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            e.save(path)
            content = Path(path).read_text(encoding="utf-8")
            assert "Save Test" in content
            assert "<?xml" in content
        finally:
            os.unlink(path)

    def test_save_html(self):
        e = SchematicEngine()
        e.add_node(ServiceNode(id="s", label="HTML Test"))
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            e.save(path, format="html")
            content = Path(path).read_text(encoding="utf-8")
            assert "<!DOCTYPE html>" in content
            assert "HTML Test" in content
        finally:
            os.unlink(path)


class TestGenerateFunctions:
    """Test convenience generation functions."""

    def test_generate_system_diagram(self):
        svg = generate_system_diagram(
            title="Test System",
            services=["API", "Database", "Cache"],
            connections=[("API", "Database"), ("API", "Cache")],
        )
        assert "<?xml" in svg
        assert "</svg>" in svg

    def test_generate_from_system_state(self):
        svg = generate_from_system_state()
        assert "SLATE System Architecture" in svg
        assert "Dashboard" in svg
        assert "Ollama" in svg

    def test_generate_empty(self):
        svg = generate_system_diagram(title="Empty")
        assert "<?xml" in svg


# ── Library Tests ────────────────────────────────────────────────────────────

class TestLibraryComponents:
    """Test pre-built component factory functions."""

    def test_slate_dashboard(self):
        n = slate_dashboard()
        assert n.id == "dashboard"
        assert n.sublabel == ":8080"
        assert n.status == ComponentStatus.ACTIVE

    def test_slate_ollama(self):
        n = slate_ollama()
        assert n.id == "ollama"
        assert n.type == ComponentType.AI

    def test_slate_chromadb(self):
        n = slate_chromadb()
        assert n.id == "chromadb"
        assert n.type == ComponentType.DATABASE

    def test_slate_dual_gpu(self):
        n = slate_dual_gpu()
        assert n.id == "gpu-cluster"
        assert n.type == ComponentType.GPU
        assert "RTX 5070 Ti" in n.sublabel

    def test_slate_gpu_indexed(self):
        n = slate_gpu(1)
        assert n.id == "gpu-1"
        assert "GPU 1" in n.label

    def test_slate_runner(self):
        n = slate_runner()
        assert n.id == "runner"
        assert "GitHub Actions" in n.sublabel

    def test_slate_vscode(self):
        n = slate_vscode()
        assert n.id == "vscode"
        assert "@slate" in n.sublabel

    def test_custom_status(self):
        n = slate_dashboard(status=ComponentStatus.ERROR)
        assert n.status == ComponentStatus.ERROR


class TestLibraryTemplates:
    """Test diagram templates."""

    def test_system_template(self):
        comps, conns = get_slate_system_template()
        assert len(comps) >= 10
        assert len(conns) >= 10
        ids = [c.id for c in comps]
        assert "dashboard" in ids
        assert "ollama" in ids
        assert "gpu-cluster" in ids

    def test_inference_template(self):
        comps, conns = get_ai_inference_template()
        assert len(comps) >= 7
        ids = [c.id for c in comps]
        assert "model-coder" in ids
        assert "model-fast" in ids

    def test_cicd_template(self):
        comps, conns = get_cicd_pipeline_template()
        assert len(comps) >= 5
        ids = [c.id for c in comps]
        assert "runner" in ids
        assert "lint" in ids

    def test_list_templates(self):
        templates = list_templates()
        assert len(templates) >= 3
        names = [t["id"] for t in templates]
        assert "system" in names
        assert "inference" in names
        assert "cicd" in names

    def test_build_from_template_system(self):
        svg = build_from_template("system")
        assert "<?xml" in svg
        assert "Dashboard" in svg

    def test_build_from_template_inference(self):
        svg = build_from_template("inference")
        assert "<?xml" in svg
        assert "slate-coder" in svg

    def test_build_from_template_cicd(self):
        svg = build_from_template("cicd")
        assert "<?xml" in svg

    def test_build_from_unknown_template(self):
        with pytest.raises(KeyError, match="Unknown template"):
            build_from_template("nonexistent")


# ── Exporter Tests ───────────────────────────────────────────────────────────

class TestSVGExporter:
    """Test SVG file export."""

    def test_to_file(self):
        svg = "<svg><rect/></svg>"
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            result = SVGExporter.to_file(svg, path)
            assert result.exists()
            assert result.read_text(encoding="utf-8") == svg
        finally:
            os.unlink(path)


class TestHTMLExporter:
    """Test HTML export."""

    def test_wrap(self):
        svg = "<svg><rect/></svg>"
        html_str = HTMLExporter.wrap(svg, title="Test")
        assert "<!DOCTYPE html>" in html_str
        assert "Test" in html_str
        assert "<svg>" in html_str

    def test_to_file(self):
        svg = "<svg><rect/></svg>"
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            result = HTMLExporter.to_file(svg, path, title="Export Test")
            assert result.exists()
            content = result.read_text(encoding="utf-8")
            assert "Export Test" in content
        finally:
            os.unlink(path)


class TestBase64Exporter:
    """Test Base64 encoding."""

    def test_encode(self):
        svg = "<svg><rect/></svg>"
        uri = Base64Exporter.encode(svg)
        assert uri.startswith("data:image/svg+xml;base64,")

    def test_to_img_tag(self):
        svg = "<svg><rect/></svg>"
        tag = Base64Exporter.to_img_tag(svg, alt="Diagram")
        assert tag.startswith("<img")
        assert 'alt="Diagram"' in tag
        assert "data:image/svg+xml;base64," in tag


class TestMarkdownExporter:
    """Test Markdown export."""

    def test_to_inline(self):
        svg = '<?xml version="1.0"?><svg><rect/></svg>'
        inline = MarkdownExporter.to_inline(svg)
        assert not inline.startswith("<?xml")
        assert "<svg>" in inline

    def test_to_link(self):
        link = MarkdownExporter.to_link("docs/diagram.svg", alt="Architecture")
        assert "![Architecture](docs/diagram.svg)" == link

    def test_to_link_with_title(self):
        link = MarkdownExporter.to_link("img.svg", alt="Test", title="Hover text")
        assert '"Hover text"' in link


class TestJSONExporter:
    """Test JSON manifest export."""

    def test_to_manifest(self):
        svg = "<svg><rect/></svg>"
        manifest = JSONExporter.to_manifest(svg, metadata={"author": "SLATE"})
        data = json.loads(manifest)
        assert data["format"] == "svg"
        assert data["sdk"] == "slate-schematic-sdk"
        assert data["metadata"]["author"] == "SLATE"
        assert data["content"] == svg
        assert data["svg_length"] == len(svg)

    def test_to_file(self):
        svg = "<svg><rect/></svg>"
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            result = JSONExporter.to_file(svg, path)
            assert result.exists()
            data = json.loads(result.read_text(encoding="utf-8"))
            assert data["content"] == svg
        finally:
            os.unlink(path)


# ── Integration Tests ────────────────────────────────────────────────────────

class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_pipeline(self):
        """Complete pipeline: config -> nodes -> connections -> layout -> render."""
        config = SchematicConfig(
            title="Integration Test",
            width=800,
            height=500,
            version_badge="v1.0",
        )
        engine = SchematicEngine(config)
        engine.add_node(ServiceNode(id="api", label="API Server", sublabel=":3000", layer=0))
        engine.add_node(DatabaseNode(id="db", label="PostgreSQL", sublabel=":5432", layer=1))
        engine.add_node(GPUNode(id="gpu", label="GPU", sublabel="CUDA 12.8", layer=2))
        engine.add_connector(FlowConnector(id="c1", from_node="api", to_node="db", label="SQL"))
        engine.add_connector(FlowConnector(id="c2", from_node="api", to_node="gpu", label="Compute"))
        engine.apply_layout()
        svg = engine.render_svg()

        # Verify output
        assert svg.startswith("<?xml")
        assert "</svg>" in svg
        assert "API Server" in svg
        assert "PostgreSQL" in svg
        assert "SQL" in svg
        assert 'data-id="api"' in svg
        assert 'data-id="db"' in svg
        assert 'v1.0' in svg
        assert "viewBox" in svg
        assert "Integration Test" in svg

    def test_all_node_types_render(self):
        """All 7 node types should render successfully."""
        engine = SchematicEngine(SchematicConfig(width=1200, height=400))
        nodes = [
            ServiceNode(id="svc", label="SVC"),
            DatabaseNode(id="db", label="DB"),
            GPUNode(id="gpu", label="GPU"),
            AINode(id="ai", label="AI"),
            APINode(id="api", label="API"),
            QueueNode(id="q", label="Queue"),
            ExternalNode(id="ext", label="External"),
        ]
        for n in nodes:
            engine.add_node(n)
        engine.set_layout("grid", columns=4)
        svg = engine.render_svg()
        for n in nodes:
            assert n.label in svg

    def test_template_to_file(self):
        """Template generation and file export."""
        svg = build_from_template("system")
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            SVGExporter.to_file(svg, path)
            content = Path(path).read_text(encoding="utf-8")
            assert len(content) > 1000  # Reasonable SVG size
            assert "Dashboard" in content
        finally:
            os.unlink(path)

    def test_different_themes(self):
        """All themes should produce valid SVG."""
        for theme in ("blueprint", "dark", "light"):
            engine = SchematicEngine(SchematicConfig(theme=theme))
            engine.add_node(ServiceNode(id="s", label="Test"))
            svg = engine.render_svg()
            assert "<?xml" in svg
            assert "</svg>" in svg

    def test_different_layouts(self):
        """All layouts should produce valid SVG."""
        for layout in ("hierarchical", "force", "grid"):
            engine = SchematicEngine()
            engine.add_node(ServiceNode(id="a", label="A"))
            engine.add_node(ServiceNode(id="b", label="B"))
            engine.add_connector(FlowConnector(id="c", from_node="a", to_node="b"))
            engine.set_layout(layout)
            svg = engine.render_svg()
            assert "<?xml" in svg
