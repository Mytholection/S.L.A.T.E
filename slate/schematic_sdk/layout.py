"""
SLATE Schematic SDK - Layout Algorithms

Automatic positioning algorithms for schematic components.
Part of SLATE Generative UI protocols.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Literal, Tuple
import math

from .components import Component, Connection, SchematicConfig


@dataclass
class LayoutResult:
    """Result of layout calculation."""
    positions: Dict[str, Tuple[float, float]]
    bounds: Tuple[float, float, float, float]  # x, y, width, height


class LayoutEngine(ABC):
    """Abstract base class for layout algorithms."""

    @abstractmethod
    def calculate_positions(
        self,
        components: List[Component],
        connections: List[Connection],
        config: SchematicConfig
    ) -> LayoutResult:
        """Calculate positions for all components."""
        pass


class HierarchicalLayout(LayoutEngine):
    """
    Hierarchical layout arranges components in layers.
    Best for: Service architectures, layer diagrams.
    """

    def __init__(
        self,
        direction: Literal["TB", "BT", "LR", "RL"] = "TB",
        layer_spacing: int = 120,
        node_spacing: int = 100,
        align: Literal["center", "left", "right"] = "center"
    ):
        self.direction = direction
        self.layer_spacing = layer_spacing
        self.node_spacing = node_spacing
        self.align = align

    def calculate_positions(
        self,
        components: List[Component],
        connections: List[Connection],
        config: SchematicConfig
    ) -> LayoutResult:
        """Calculate hierarchical positions."""
        positions: Dict[str, Tuple[float, float]] = {}

        if not components:
            return LayoutResult(positions={}, bounds=(0, 0, config.width, config.height))

        # Group components by layer
        layers: Dict[int, List[Component]] = {}
        for comp in components:
            layer = comp.layer
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(comp)

        # Sort layers
        sorted_layers = sorted(layers.keys())

        # Calculate available space
        padding = config.padding
        available_width = config.width - (padding * 2)
        available_height = config.height - (padding * 2)

        # Calculate layer positions
        num_layers = len(sorted_layers)
        if self.direction in ("TB", "BT"):
            layer_height = available_height / max(num_layers, 1)
        else:
            layer_width = available_width / max(num_layers, 1)

        for layer_idx, layer_num in enumerate(sorted_layers):
            layer_components = layers[layer_num]
            num_nodes = len(layer_components)

            for node_idx, comp in enumerate(layer_components):
                if self.direction in ("TB", "BT"):
                    # Top to bottom or bottom to top
                    if self.direction == "TB":
                        y = padding + (layer_idx * layer_height) + (layer_height / 2)
                    else:
                        y = config.height - padding - (layer_idx * layer_height) - (layer_height / 2)

                    # Distribute nodes horizontally
                    node_width = available_width / max(num_nodes, 1)
                    x = padding + (node_idx * node_width) + (node_width / 2)

                    # Apply alignment
                    if self.align == "left":
                        x = padding + (node_idx * self.node_spacing) + (comp.size[0] / 2 if comp.size else 70)
                    elif self.align == "right":
                        x = config.width - padding - ((num_nodes - 1 - node_idx) * self.node_spacing) - (comp.size[0] / 2 if comp.size else 70)
                else:
                    # Left to right or right to left
                    if self.direction == "LR":
                        x = padding + (layer_idx * layer_width) + (layer_width / 2)
                    else:
                        x = config.width - padding - (layer_idx * layer_width) - (layer_width / 2)

                    # Distribute nodes vertically
                    node_height = available_height / max(num_nodes, 1)
                    y = padding + (node_idx * node_height) + (node_height / 2)

                positions[comp.id] = (x, y)

        # Calculate bounds
        if positions:
            xs = [p[0] for p in positions.values()]
            ys = [p[1] for p in positions.values()]
            bounds = (min(xs), min(ys), max(xs), max(ys))
        else:
            bounds = (0, 0, config.width, config.height)

        return LayoutResult(positions=positions, bounds=bounds)


class ForceDirectedLayout(LayoutEngine):
    """
    Force-directed layout uses physics simulation.
    Best for: Network diagrams, integration maps.
    """

    def __init__(
        self,
        iterations: int = 100,
        repulsion_strength: float = 500,
        attraction_strength: float = 0.1,
        center_gravity: float = 0.1,
        damping: float = 0.9
    ):
        self.iterations = iterations
        self.repulsion_strength = repulsion_strength
        self.attraction_strength = attraction_strength
        self.center_gravity = center_gravity
        self.damping = damping

    def calculate_positions(
        self,
        components: List[Component],
        connections: List[Connection],
        config: SchematicConfig
    ) -> LayoutResult:
        """Calculate force-directed positions."""
        if not components:
            return LayoutResult(positions={}, bounds=(0, 0, config.width, config.height))

        # Initialize random positions
        import random
        random.seed(42)  # Reproducible layout

        center_x = config.width / 2
        center_y = config.height / 2
        radius = min(config.width, config.height) / 3

        positions: Dict[str, List[float]] = {}
        velocities: Dict[str, List[float]] = {}

        for i, comp in enumerate(components):
            if comp.position:
                positions[comp.id] = list(comp.position)
            else:
                angle = (2 * math.pi * i) / len(components)
                x = center_x + radius * math.cos(angle) * random.uniform(0.5, 1.0)
                y = center_y + radius * math.sin(angle) * random.uniform(0.5, 1.0)
                positions[comp.id] = [x, y]
            velocities[comp.id] = [0.0, 0.0]

        # Build edge lookup
        edges = [(c.from_node, c.to_node) for c in connections]

        # Simulation loop
        for _ in range(self.iterations):
            forces: Dict[str, List[float]] = {c.id: [0.0, 0.0] for c in components}

            # Repulsion between all nodes
            for i, comp1 in enumerate(components):
                for comp2 in components[i + 1:]:
                    dx = positions[comp2.id][0] - positions[comp1.id][0]
                    dy = positions[comp2.id][1] - positions[comp1.id][1]
                    dist = math.sqrt(dx * dx + dy * dy) + 0.01

                    force = self.repulsion_strength / (dist * dist)
                    fx = force * dx / dist
                    fy = force * dy / dist

                    forces[comp1.id][0] -= fx
                    forces[comp1.id][1] -= fy
                    forces[comp2.id][0] += fx
                    forces[comp2.id][1] += fy

            # Attraction along edges
            for from_id, to_id in edges:
                if from_id in positions and to_id in positions:
                    dx = positions[to_id][0] - positions[from_id][0]
                    dy = positions[to_id][1] - positions[from_id][1]
                    dist = math.sqrt(dx * dx + dy * dy) + 0.01

                    force = dist * self.attraction_strength
                    fx = force * dx / dist
                    fy = force * dy / dist

                    forces[from_id][0] += fx
                    forces[from_id][1] += fy
                    forces[to_id][0] -= fx
                    forces[to_id][1] -= fy

            # Center gravity
            for comp in components:
                dx = center_x - positions[comp.id][0]
                dy = center_y - positions[comp.id][1]
                forces[comp.id][0] += dx * self.center_gravity
                forces[comp.id][1] += dy * self.center_gravity

            # Apply forces with damping
            for comp in components:
                velocities[comp.id][0] = (velocities[comp.id][0] + forces[comp.id][0]) * self.damping
                velocities[comp.id][1] = (velocities[comp.id][1] + forces[comp.id][1]) * self.damping
                positions[comp.id][0] += velocities[comp.id][0]
                positions[comp.id][1] += velocities[comp.id][1]

                # Constrain to bounds
                padding = config.padding + 50
                positions[comp.id][0] = max(padding, min(config.width - padding, positions[comp.id][0]))
                positions[comp.id][1] = max(padding, min(config.height - padding, positions[comp.id][1]))

        # Convert to tuples
        result_positions = {k: (v[0], v[1]) for k, v in positions.items()}

        # Calculate bounds
        xs = [p[0] for p in result_positions.values()]
        ys = [p[1] for p in result_positions.values()]
        bounds = (min(xs), min(ys), max(xs), max(ys))

        return LayoutResult(positions=result_positions, bounds=bounds)


class GridLayout(LayoutEngine):
    """
    Grid layout snaps components to a grid.
    Best for: Component libraries, dashboards.
    """

    def __init__(
        self,
        columns: int = 4,
        cell_width: int = 200,
        cell_height: int = 150,
        gap: int = 20
    ):
        self.columns = columns
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.gap = gap

    def calculate_positions(
        self,
        components: List[Component],
        connections: List[Connection],
        config: SchematicConfig
    ) -> LayoutResult:
        """Calculate grid positions."""
        positions: Dict[str, Tuple[float, float]] = {}

        if not components:
            return LayoutResult(positions={}, bounds=(0, 0, config.width, config.height))

        padding = config.padding

        for idx, comp in enumerate(components):
            col = idx % self.columns
            row = idx // self.columns

            x = padding + (col * (self.cell_width + self.gap)) + (self.cell_width / 2)
            y = padding + (row * (self.cell_height + self.gap)) + (self.cell_height / 2)

            positions[comp.id] = (x, y)

        # Calculate bounds
        xs = [p[0] for p in positions.values()]
        ys = [p[1] for p in positions.values()]
        bounds = (min(xs), min(ys), max(xs), max(ys))

        return LayoutResult(positions=positions, bounds=bounds)


def get_layout_engine(
    layout_type: str,
    **kwargs
) -> LayoutEngine:
    """Factory function to get layout engine by name."""
    engines = {
        "hierarchical": HierarchicalLayout,
        "force": ForceDirectedLayout,
        "grid": GridLayout,
    }

    if layout_type not in engines:
        raise ValueError(f"Unknown layout type: {layout_type}. Available: {list(engines.keys())}")

    return engines[layout_type](**kwargs)
