"""
SLATE Schematic SDK - Component Definitions

Circuit-board style components for system diagram generation.
Part of SLATE Generative UI protocols.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple
from enum import Enum


class ComponentType(str, Enum):
    """Component type enumeration."""
    SERVICE = "service"
    DATABASE = "database"
    GPU = "gpu"
    AI = "ai"
    API = "api"
    QUEUE = "queue"
    EXTERNAL = "external"
    TERMINAL = "terminal"


class ConnectionStyle(str, Enum):
    """Connection line styles."""
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"


class ComponentStatus(str, Enum):
    """Component status for color coding."""
    ACTIVE = "active"
    PENDING = "pending"
    ERROR = "error"
    INACTIVE = "inactive"


class PortPosition(str, Enum):
    """Port positions on components."""
    TOP = "top"
    RIGHT = "right"
    BOTTOM = "bottom"
    LEFT = "left"


@dataclass
class Port:
    """Connection port on a component."""
    id: str
    position: PortPosition = PortPosition.RIGHT
    type: Literal["input", "output", "bidirectional"] = "bidirectional"


@dataclass
class Component:
    """Base component class for all schematic elements."""
    id: str
    type: ComponentType
    label: str
    sublabel: str = ""
    position: Optional[Tuple[float, float]] = None
    size: Optional[Tuple[float, float]] = None
    status: ComponentStatus = ComponentStatus.ACTIVE
    ports: List[Port] = field(default_factory=list)
    layer: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.ports:
            # Default ports based on component type
            self.ports = [
                Port(id="left", position=PortPosition.LEFT, type="input"),
                Port(id="right", position=PortPosition.RIGHT, type="output"),
            ]


@dataclass
class ServiceNode(Component):
    """Microservice/server component (rounded rectangle)."""
    type: ComponentType = field(default=ComponentType.SERVICE, init=False)
    shape: str = "rounded_rect"
    default_size: Tuple[float, float] = (140, 60)

    def __post_init__(self):
        super().__post_init__()
        if self.size is None:
            self.size = self.default_size


@dataclass
class DatabaseNode(Component):
    """Data store component (cylinder shape)."""
    type: ComponentType = field(default=ComponentType.DATABASE, init=False)
    shape: str = "cylinder"
    default_size: Tuple[float, float] = (100, 80)

    def __post_init__(self):
        super().__post_init__()
        if self.size is None:
            self.size = self.default_size


@dataclass
class GPUNode(Component):
    """GPU/compute resource component (hexagon shape)."""
    type: ComponentType = field(default=ComponentType.GPU, init=False)
    shape: str = "hexagon"
    default_size: Tuple[float, float] = (120, 80)

    def __post_init__(self):
        super().__post_init__()
        if self.size is None:
            self.size = self.default_size


@dataclass
class AINode(Component):
    """AI/ML service component (rounded rect with brain accent)."""
    type: ComponentType = field(default=ComponentType.AI, init=False)
    shape: str = "ai_node"
    default_size: Tuple[float, float] = (140, 70)

    def __post_init__(self):
        super().__post_init__()
        if self.size is None:
            self.size = self.default_size


@dataclass
class APINode(Component):
    """API endpoint component (rectangle with port badge)."""
    type: ComponentType = field(default=ComponentType.API, init=False)
    shape: str = "api_node"
    port_number: Optional[int] = None
    default_size: Tuple[float, float] = (120, 50)

    def __post_init__(self):
        super().__post_init__()
        if self.size is None:
            self.size = self.default_size


@dataclass
class QueueNode(Component):
    """Message queue component (parallelogram shape)."""
    type: ComponentType = field(default=ComponentType.QUEUE, init=False)
    shape: str = "parallelogram"
    default_size: Tuple[float, float] = (130, 50)

    def __post_init__(self):
        super().__post_init__()
        if self.size is None:
            self.size = self.default_size


@dataclass
class ExternalNode(Component):
    """External service component (dashed border)."""
    type: ComponentType = field(default=ComponentType.EXTERNAL, init=False)
    shape: str = "external"
    default_size: Tuple[float, float] = (120, 60)

    def __post_init__(self):
        super().__post_init__()
        if self.size is None:
            self.size = self.default_size


@dataclass
class Connection:
    """Connection between components."""
    id: str
    from_node: str
    to_node: str
    from_port: str = "right"
    to_port: str = "left"
    label: str = ""
    style: ConnectionStyle = ConnectionStyle.SOLID
    animated: bool = False
    bidirectional: bool = False
    color_override: Optional[str] = None


@dataclass
class FlowConnector(Connection):
    """Standard data flow connector with arrow."""
    style: ConnectionStyle = ConnectionStyle.SOLID


@dataclass
class DashedConnector(Connection):
    """Dashed connector for optional/async flows."""
    style: ConnectionStyle = ConnectionStyle.DASHED


@dataclass
class DataBus(Connection):
    """Multi-connection data bus."""
    connected_nodes: List[str] = field(default_factory=list)
    bus_width: float = 4.0


@dataclass
class InputTerminal:
    """External input terminal."""
    id: str
    label: str
    position: Optional[Tuple[float, float]] = None
    connected_to: Optional[str] = None


@dataclass
class OutputTerminal:
    """External output terminal."""
    id: str
    label: str
    position: Optional[Tuple[float, float]] = None
    connected_from: Optional[str] = None


@dataclass
class Annotation:
    """Text annotation for diagrams."""
    id: str
    text: str
    position: Tuple[float, float]
    style: Literal["title", "subtitle", "label", "note"] = "label"
    anchor: Literal["start", "middle", "end"] = "start"


@dataclass
class Layer:
    """Group of components at the same hierarchical level."""
    id: str
    name: str
    components: List[Component] = field(default_factory=list)
    y_position: Optional[float] = None


@dataclass
class SchematicConfig:
    """Configuration for schematic generation."""
    width: int = 900
    height: int = 600
    title: str = "SLATE Schematic"
    theme: str = "blueprint"
    layout: str = "hierarchical"
    show_grid: bool = True
    show_legend: bool = True
    show_title: bool = True
    version_badge: str = ""
    padding: int = 40
    layer_spacing: int = 120
    node_spacing: int = 100
