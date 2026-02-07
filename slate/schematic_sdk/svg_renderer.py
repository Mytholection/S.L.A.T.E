"""
SLATE Schematic SDK - SVG Renderer

Generates GitHub-compatible SVG output with inline styles.
Part of SLATE Generative UI protocols.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import html

from .components import (
    Component, Connection, SchematicConfig,
    ComponentType, ConnectionStyle, Annotation
)
from .theme import ThemeManager, SchematicTheme


class SVGRenderer:
    """Renders schematic components to SVG."""

    def __init__(self, theme_manager: ThemeManager):
        self.theme = theme_manager.theme
        self.tm = theme_manager

    def render(
        self,
        components: List[Component],
        connections: List[Connection],
        positions: Dict[str, Tuple[float, float]],
        config: SchematicConfig,
        annotations: Optional[List[Annotation]] = None
    ) -> str:
        """Render complete SVG document."""
        parts = [
            self._render_header(config),
            self._render_defs(config),
            self._render_background(config),
        ]

        if config.show_grid:
            parts.append(self._render_grid(config))

        parts.append(self._render_connections(connections, positions, components))
        parts.append(self._render_components(components, positions))

        if annotations:
            parts.append(self._render_annotations(annotations))

        if config.show_title:
            parts.append(self._render_title(config))

        if config.show_legend:
            parts.append(self._render_legend(config))

        if config.version_badge:
            parts.append(self._render_version_badge(config))

        parts.append(self._render_footer())

        return "\n".join(parts)

    def _render_header(self, config: SchematicConfig) -> str:
        """Render SVG header."""
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{config.width}" height="{config.height}" viewBox="0 0 {config.width} {config.height}"
     xmlns="http://www.w3.org/2000/svg"
     role="img" aria-label="{html.escape(config.title)}">'''

    def _render_footer(self) -> str:
        """Render SVG footer."""
        return "</svg>"

    def _render_defs(self, config: SchematicConfig) -> str:
        """Render SVG definitions (gradients, filters, markers)."""
        c = self.theme.colors
        e = self.theme.effects

        return f'''
  <defs>
    <!-- Background Gradient -->
    <linearGradient id="bgGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{c.background};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{c.background_gradient_end};stop-opacity:1" />
    </linearGradient>

    <!-- Primary Accent Gradient -->
    <linearGradient id="primaryGradient" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:{c.primary};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{c.primary_light};stop-opacity:1" />
    </linearGradient>

    <!-- Status Gradients -->
    <linearGradient id="activeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:{c.status_active};stop-opacity:1" />
      <stop offset="100%" style="stop-color:#4ADE80;stop-opacity:1" />
    </linearGradient>

    <!-- Glow Effect -->
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="{e.glow_blur}" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <!-- Drop Shadow -->
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="{e.shadow_dx}" dy="{e.shadow_dy}" stdDeviation="{e.shadow_blur}"
                    flood-color="{e.shadow_color}" flood-opacity="{e.shadow_opacity}"/>
    </filter>

    <!-- Arrow Marker -->
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="{c.connection_default}"/>
    </marker>

    <!-- Arrow Marker (Active) -->
    <marker id="arrowhead-active" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="{c.status_active}"/>
    </marker>

    <!-- Grid Pattern -->
    <pattern id="gridPattern" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="{c.grid_lines}" stroke-width="0.5" opacity="{c.grid_opacity}"/>
    </pattern>
  </defs>'''

    def _render_background(self, config: SchematicConfig) -> str:
        """Render background rectangle."""
        return f'''
  <!-- Background -->
  <rect width="{config.width}" height="{config.height}" fill="url(#bgGradient)"/>'''

    def _render_grid(self, config: SchematicConfig) -> str:
        """Render grid overlay."""
        return f'''
  <!-- Grid Overlay -->
  <rect width="{config.width}" height="{config.height}" fill="url(#gridPattern)" opacity="0.5"/>'''

    def _render_components(
        self,
        components: List[Component],
        positions: Dict[str, Tuple[float, float]]
    ) -> str:
        """Render all components."""
        parts = ["\n  <!-- Components Layer -->", "  <g class=\"components-layer\" filter=\"url(#shadow)\">"]

        for comp in components:
            if comp.id not in positions:
                continue
            x, y = positions[comp.id]
            parts.append(self._render_component(comp, x, y))

        parts.append("  </g>")
        return "\n".join(parts)

    def _render_component(self, comp: Component, x: float, y: float) -> str:
        """Render a single component."""
        c = self.theme.colors
        t = self.theme.typography
        e = self.theme.effects

        width = comp.size[0] if comp.size else 140
        height = comp.size[1] if comp.size else 60
        half_w = width / 2
        half_h = height / 2

        fill = self.tm.get_component_fill(comp.type.value)
        border = self.tm.get_component_border(comp.type.value, comp.status.value)
        status_color = self.tm.get_status_color(comp.status.value)

        # Render based on component type
        if comp.type == ComponentType.DATABASE:
            return self._render_cylinder(comp, x, y, width, height, fill, border, status_color)
        elif comp.type == ComponentType.GPU:
            return self._render_hexagon(comp, x, y, width, height, fill, border, status_color)
        elif comp.type == ComponentType.QUEUE:
            return self._render_parallelogram(comp, x, y, width, height, fill, border, status_color)
        elif comp.type == ComponentType.EXTERNAL:
            return self._render_external(comp, x, y, width, height, border, status_color)
        else:
            # Default: rounded rectangle
            return self._render_rounded_rect(comp, x, y, width, height, fill, border, status_color)

    def _render_rounded_rect(
        self, comp: Component, x: float, y: float,
        width: float, height: float, fill: str, border: str, status_color: str
    ) -> str:
        """Render rounded rectangle component."""
        c = self.theme.colors
        t = self.theme.typography
        e = self.theme.effects
        rx = x - width / 2
        ry = y - height / 2

        # Status indicator
        indicator = f'''
      <circle cx="{rx + 12}" cy="{ry + 12}" r="5" fill="{status_color}"/>'''

        # AI icon for AI nodes
        icon = ""
        if comp.type == ComponentType.AI:
            icon = f'''
      <text x="{rx + width - 15}" y="{ry + 18}" font-family="{t.font_display}" font-size="14" fill="{c.primary}">&#129504;</text>'''

        return f'''
    <g class="component" data-id="{comp.id}" data-type="{comp.type.value}">
      <rect x="{rx}" y="{ry}" width="{width}" height="{height}"
            rx="{e.radius_md}" fill="{fill}" stroke="{border}" stroke-width="2"/>
      {indicator}{icon}
      <text x="{x}" y="{y - 2}" text-anchor="middle"
            font-family="{t.font_display}" font-size="{t.label_size}" font-weight="{t.weight_semibold}"
            fill="{c.text_primary}">{html.escape(comp.label)}</text>
      <text x="{x}" y="{y + 14}" text-anchor="middle"
            font-family="{t.font_mono}" font-size="{t.sublabel_size}"
            fill="{c.text_secondary}">{html.escape(comp.sublabel)}</text>
    </g>'''

    def _render_cylinder(
        self, comp: Component, x: float, y: float,
        width: float, height: float, fill: str, border: str, status_color: str
    ) -> str:
        """Render cylinder (database) component."""
        c = self.theme.colors
        t = self.theme.typography
        rx = x - width / 2
        ry = y - height / 2
        ellipse_ry = 10

        return f'''
    <g class="component" data-id="{comp.id}" data-type="database">
      <!-- Cylinder body -->
      <path d="M {rx} {ry + ellipse_ry}
               L {rx} {ry + height - ellipse_ry}
               A {width/2} {ellipse_ry} 0 0 0 {rx + width} {ry + height - ellipse_ry}
               L {rx + width} {ry + ellipse_ry}
               A {width/2} {ellipse_ry} 0 0 0 {rx} {ry + ellipse_ry}"
            fill="{fill}" stroke="{border}" stroke-width="2"/>
      <!-- Top ellipse -->
      <ellipse cx="{x}" cy="{ry + ellipse_ry}" rx="{width/2}" ry="{ellipse_ry}"
               fill="{fill}" stroke="{border}" stroke-width="2"/>
      <circle cx="{rx + 12}" cy="{ry + ellipse_ry + 8}" r="4" fill="{status_color}"/>
      <text x="{x}" y="{y + 5}" text-anchor="middle"
            font-family="{t.font_display}" font-size="{t.label_size}" font-weight="{t.weight_semibold}"
            fill="{c.text_primary}">{html.escape(comp.label)}</text>
      <text x="{x}" y="{y + 20}" text-anchor="middle"
            font-family="{t.font_mono}" font-size="{t.sublabel_size}"
            fill="{c.text_secondary}">{html.escape(comp.sublabel)}</text>
    </g>'''

    def _render_hexagon(
        self, comp: Component, x: float, y: float,
        width: float, height: float, fill: str, border: str, status_color: str
    ) -> str:
        """Render hexagon (GPU) component."""
        c = self.theme.colors
        t = self.theme.typography
        # Hexagon points
        hw = width / 2
        hh = height / 2
        indent = width * 0.2
        points = f"{x - hw + indent},{y - hh} {x + hw - indent},{y - hh} {x + hw},{y} {x + hw - indent},{y + hh} {x - hw + indent},{y + hh} {x - hw},{y}"

        return f'''
    <g class="component" data-id="{comp.id}" data-type="gpu">
      <polygon points="{points}" fill="{fill}" stroke="{border}" stroke-width="2"/>
      <circle cx="{x - hw + indent + 10}" cy="{y - hh + 12}" r="4" fill="{status_color}"/>
      <text x="{x}" y="{y - 2}" text-anchor="middle"
            font-family="{t.font_display}" font-size="{t.label_size}" font-weight="{t.weight_semibold}"
            fill="{c.text_primary}">{html.escape(comp.label)}</text>
      <text x="{x}" y="{y + 14}" text-anchor="middle"
            font-family="{t.font_mono}" font-size="{t.sublabel_size}"
            fill="{c.text_secondary}">{html.escape(comp.sublabel)}</text>
    </g>'''

    def _render_parallelogram(
        self, comp: Component, x: float, y: float,
        width: float, height: float, fill: str, border: str, status_color: str
    ) -> str:
        """Render parallelogram (queue) component."""
        c = self.theme.colors
        t = self.theme.typography
        hw = width / 2
        hh = height / 2
        skew = 15
        points = f"{x - hw + skew},{y - hh} {x + hw + skew},{y - hh} {x + hw - skew},{y + hh} {x - hw - skew},{y + hh}"

        return f'''
    <g class="component" data-id="{comp.id}" data-type="queue">
      <polygon points="{points}" fill="{fill}" stroke="{border}" stroke-width="2"/>
      <circle cx="{x - hw + skew + 10}" cy="{y - hh + 10}" r="4" fill="{status_color}"/>
      <text x="{x}" y="{y + 4}" text-anchor="middle"
            font-family="{t.font_display}" font-size="{t.label_size}" font-weight="{t.weight_semibold}"
            fill="{c.text_primary}">{html.escape(comp.label)}</text>
    </g>'''

    def _render_external(
        self, comp: Component, x: float, y: float,
        width: float, height: float, border: str, status_color: str
    ) -> str:
        """Render external service (dashed border)."""
        c = self.theme.colors
        t = self.theme.typography
        e = self.theme.effects
        rx = x - width / 2
        ry = y - height / 2

        return f'''
    <g class="component" data-id="{comp.id}" data-type="external">
      <rect x="{rx}" y="{ry}" width="{width}" height="{height}"
            rx="{e.radius_md}" fill="none" stroke="{c.text_muted}" stroke-width="2" stroke-dasharray="5,5"/>
      <circle cx="{rx + 12}" cy="{ry + 12}" r="4" fill="{status_color}"/>
      <text x="{x}" y="{y}" text-anchor="middle"
            font-family="{t.font_display}" font-size="{t.label_size}" font-weight="{t.weight_semibold}"
            fill="{c.text_secondary}">{html.escape(comp.label)}</text>
    </g>'''

    def _render_connections(
        self,
        connections: List[Connection],
        positions: Dict[str, Tuple[float, float]],
        components: List[Component]
    ) -> str:
        """Render all connections."""
        parts = ["\n  <!-- Connections Layer -->", "  <g class=\"connections-layer\">"]

        # Create component lookup for sizes
        comp_lookup = {c.id: c for c in components}

        for conn in connections:
            if conn.from_node not in positions or conn.to_node not in positions:
                continue

            from_pos = positions[conn.from_node]
            to_pos = positions[conn.to_node]

            # Adjust endpoints based on component sizes
            from_comp = comp_lookup.get(conn.from_node)
            to_comp = comp_lookup.get(conn.to_node)

            from_x, from_y = from_pos
            to_x, to_y = to_pos

            # Offset from component edge
            if from_comp and from_comp.size:
                from_x += from_comp.size[0] / 2
            if to_comp and to_comp.size:
                to_x -= to_comp.size[0] / 2

            parts.append(self._render_connection(conn, from_x, from_y, to_x, to_y))

        parts.append("  </g>")
        return "\n".join(parts)

    def _render_connection(
        self, conn: Connection,
        x1: float, y1: float, x2: float, y2: float
    ) -> str:
        """Render a single connection."""
        c = self.theme.colors
        t = self.theme.typography

        color = conn.color_override or c.connection_default
        marker = "arrowhead"
        stroke_dasharray = ""

        if conn.style == ConnectionStyle.DASHED:
            stroke_dasharray = 'stroke-dasharray="5,5"'
        elif conn.style == ConnectionStyle.DOTTED:
            stroke_dasharray = 'stroke-dasharray="2,2"'

        # Create curved path for better aesthetics
        mid_x = (x1 + x2) / 2
        ctrl_offset = abs(y2 - y1) * 0.3

        path = f"M {x1} {y1} C {mid_x} {y1}, {mid_x} {y2}, {x2} {y2}"

        label_part = ""
        if conn.label:
            label_x = mid_x
            label_y = (y1 + y2) / 2 - 8
            label_part = f'''
      <text x="{label_x}" y="{label_y}" text-anchor="middle"
            font-family="{t.font_mono}" font-size="{t.sublabel_size}"
            fill="{c.text_secondary}">{html.escape(conn.label)}</text>'''

        return f'''
    <g class="connection" data-from="{conn.from_node}" data-to="{conn.to_node}">
      <path d="{path}" fill="none" stroke="{color}" stroke-width="2"
            marker-end="url(#{marker})" {stroke_dasharray}/>
      {label_part}
    </g>'''

    def _render_title(self, config: SchematicConfig) -> str:
        """Render diagram title."""
        c = self.theme.colors
        t = self.theme.typography

        return f'''
  <!-- Title -->
  <text x="{config.padding}" y="{config.padding + 5}"
        font-family="{t.font_display}" font-size="{t.title_size}" font-weight="{t.weight_bold}"
        fill="{c.text_primary}">{html.escape(config.title)}</text>'''

    def _render_legend(self, config: SchematicConfig) -> str:
        """Render status legend."""
        c = self.theme.colors
        t = self.theme.typography

        legend_x = config.width - 150
        legend_y = config.height - 80

        return f'''
  <!-- Legend -->
  <g class="legend" transform="translate({legend_x}, {legend_y})">
    <text x="0" y="0" font-family="{t.font_display}" font-size="{t.sublabel_size}" font-weight="{t.weight_semibold}" fill="{c.text_secondary}">Status</text>
    <circle cx="8" cy="15" r="4" fill="{c.status_active}"/>
    <text x="18" y="18" font-family="{t.font_mono}" font-size="{t.sublabel_size}" fill="{c.text_secondary}">Active</text>
    <circle cx="8" cy="30" r="4" fill="{c.status_pending}"/>
    <text x="18" y="33" font-family="{t.font_mono}" font-size="{t.sublabel_size}" fill="{c.text_secondary}">Pending</text>
    <circle cx="8" cy="45" r="4" fill="{c.status_error}"/>
    <text x="18" y="48" font-family="{t.font_mono}" font-size="{t.sublabel_size}" fill="{c.text_secondary}">Error</text>
  </g>'''

    def _render_version_badge(self, config: SchematicConfig) -> str:
        """Render version badge."""
        c = self.theme.colors
        t = self.theme.typography

        badge_x = config.width - 110
        badge_y = config.padding

        return f'''
  <!-- Version Badge -->
  <g class="version-badge">
    <rect x="{badge_x}" y="{badge_y}" width="90" height="24" rx="12" fill="{c.primary}"/>
    <text x="{badge_x + 45}" y="{badge_y + 16}" text-anchor="middle"
          font-family="{t.font_display}" font-size="{t.badge_size}" font-weight="{t.weight_semibold}"
          fill="#FFFFFF">{html.escape(config.version_badge)}</text>
  </g>'''

    def _render_annotations(self, annotations: List[Annotation]) -> str:
        """Render text annotations."""
        c = self.theme.colors
        t = self.theme.typography
        parts = ["\n  <!-- Annotations Layer -->", "  <g class=\"annotations-layer\">"]

        for ann in annotations:
            size = t.label_size
            weight = t.weight_regular
            color = c.text_secondary

            if ann.style == "title":
                size = t.title_size
                weight = t.weight_bold
                color = c.text_primary
            elif ann.style == "subtitle":
                size = t.subtitle_size
                weight = t.weight_semibold
            elif ann.style == "note":
                color = c.text_muted

            parts.append(f'''
    <text x="{ann.position[0]}" y="{ann.position[1]}" text-anchor="{ann.anchor}"
          font-family="{t.font_display}" font-size="{size}" font-weight="{weight}"
          fill="{color}">{html.escape(ann.text)}</text>''')

        parts.append("  </g>")
        return "\n".join(parts)
