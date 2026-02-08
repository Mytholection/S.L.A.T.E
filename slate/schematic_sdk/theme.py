"""
SLATE Schematic SDK - Theme Integration

Integrates with locked design tokens (v3.0.0) for consistent theming.
Part of SLATE Generative UI protocols.
"""

from dataclasses import dataclass, field
from typing import Dict, Literal
import sys
from pathlib import Path

# Add workspace root for imports
WORKSPACE_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))


@dataclass
class SchematicColors:
    """Color palette for schematic rendering."""
    # Background
    background: str = "#0D1B2A"
    background_gradient_end: str = "#1B3A4B"

    # Grid
    grid_lines: str = "#1B3A4B"
    grid_opacity: float = 0.3

    # Primary accent (Anthropic rust)
    primary: str = "#B85A3C"
    primary_light: str = "#D4785A"
    primary_dark: str = "#8B4530"

    # Blueprint accents
    blueprint_accent: str = "#98C1D9"
    blueprint_node: str = "#E0FBFC"

    # Surface colors
    surface: str = "#1A1816"
    surface_container: str = "#2A2624"
    surface_elevated: str = "#3A3634"

    # Status colors
    status_active: str = "#22C55E"
    status_pending: str = "#F59E0B"
    status_error: str = "#EF4444"
    status_inactive: str = "#6B7280"

    # Component type colors
    service_fill: str = "#2A2624"
    database_fill: str = "#1E3A5F"
    gpu_fill: str = "#3D2914"
    ai_fill: str = "#3D1E10"
    api_fill: str = "#1A2436"
    queue_fill: str = "#2A2436"
    external_fill: str = "transparent"

    # Text colors
    text_primary: str = "#E8E2DE"
    text_secondary: str = "#CAC4BF"
    text_muted: str = "#6B7280"

    # Border colors
    border_default: str = "#3A3634"
    border_hover: str = "#4A4644"

    # Connection colors
    connection_default: str = "#B85A3C"
    connection_active: str = "#22C55E"
    connection_muted: str = "#6B7280"


@dataclass
class SchematicTypography:
    """Typography settings for schematic rendering."""
    font_display: str = "'Segoe UI', 'Inter', system-ui, sans-serif"
    font_mono: str = "'Consolas', 'JetBrains Mono', monospace"

    # Font sizes
    title_size: int = 24
    subtitle_size: int = 14
    label_size: int = 12
    sublabel_size: int = 10
    badge_size: int = 11

    # Font weights
    weight_bold: int = 700
    weight_semibold: int = 600
    weight_regular: int = 400


@dataclass
class SchematicEffects:
    """Visual effects for schematic rendering."""
    # Shadow
    shadow_dx: int = 2
    shadow_dy: int = 4
    shadow_blur: int = 4
    shadow_color: str = "#000000"
    shadow_opacity: float = 0.3

    # Glow
    glow_blur: int = 2

    # Border radius
    radius_sm: int = 4
    radius_md: int = 8
    radius_lg: int = 12


@dataclass
class SchematicTheme:
    """Complete theme configuration for schematics."""
    name: str = "blueprint"
    colors: SchematicColors = field(default_factory=SchematicColors)
    typography: SchematicTypography = field(default_factory=SchematicTypography)
    effects: SchematicEffects = field(default_factory=SchematicEffects)


class ThemeManager:
    """Manages schematic themes and integrates with design tokens."""

    # Pre-defined themes
    THEMES: Dict[str, Dict] = {
        "blueprint": {
            "background": "#0D1B2A",
            "background_gradient_end": "#1B3A4B",
            "grid_lines": "#1B3A4B",
            "primary": "#B85A3C",
        },
        "dark": {
            "background": "#1A1816",
            "background_gradient_end": "#2A2624",
            "grid_lines": "#3A3634",
            "primary": "#B85A3C",
        },
        "light": {
            "background": "#FBF8F6",
            "background_gradient_end": "#F0EBE7",
            "grid_lines": "#E4E0DC",
            "primary": "#B85A3C",
            "text_primary": "#1C1B1A",
            "text_secondary": "#4D4845",
            "surface_container": "#F5F2F0",
        },
    }

    def __init__(self, theme_name: Literal["blueprint", "dark", "light"] = "blueprint"):
        self.theme_name = theme_name
        self.theme = self._build_theme(theme_name)

    def _build_theme(self, theme_name: str) -> SchematicTheme:
        """Build theme from name, applying overrides."""
        colors = SchematicColors()
        typography = SchematicTypography()
        effects = SchematicEffects()

        # Apply theme-specific overrides
        if theme_name in self.THEMES:
            overrides = self.THEMES[theme_name]
            for key, value in overrides.items():
                if hasattr(colors, key):
                    setattr(colors, key, value)

        return SchematicTheme(
            name=theme_name,
            colors=colors,
            typography=typography,
            effects=effects
        )

    def get_status_color(self, status: str) -> str:
        """Get color for component status."""
        status_map = {
            "active": self.theme.colors.status_active,
            "pending": self.theme.colors.status_pending,
            "error": self.theme.colors.status_error,
            "inactive": self.theme.colors.status_inactive,
        }
        return status_map.get(status, self.theme.colors.status_inactive)

    def get_component_fill(self, component_type: str) -> str:
        """Get fill color for component type."""
        fill_map = {
            "service": self.theme.colors.service_fill,
            "database": self.theme.colors.database_fill,
            "gpu": self.theme.colors.gpu_fill,
            "ai": self.theme.colors.ai_fill,
            "api": self.theme.colors.api_fill,
            "queue": self.theme.colors.queue_fill,
            "external": self.theme.colors.external_fill,
        }
        return fill_map.get(component_type, self.theme.colors.surface_container)

    def get_component_border(self, component_type: str, status: str = "active") -> str:
        """Get border color for component."""
        if status == "active":
            return self.theme.colors.primary
        return self.get_status_color(status)


# Pre-instantiated themes for convenience
BlueprintTheme = lambda: ThemeManager("blueprint").theme
DarkTheme = lambda: ThemeManager("dark").theme
LightTheme = lambda: ThemeManager("light").theme
