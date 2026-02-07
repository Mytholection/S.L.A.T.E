#!/usr/bin/env python3
"""
SLATE Schematic SDK - CLI Tool

Generate circuit-board style system diagrams from the command line.

Usage:
    python -m slate.schematic_sdk.cli from-system --output system.svg
    python -m slate.schematic_sdk.cli from-tech-tree --output tech-tree.svg
    python -m slate.schematic_sdk.cli generate --input diagram.yaml --output diagram.svg
"""

import argparse
import json
import sys
from pathlib import Path

# Add workspace root for imports
WORKSPACE_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SLATE Schematic Diagram Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Generate from current system state:
    %(prog)s from-system --output docs/assets/system.svg

  Generate from tech tree:
    %(prog)s from-tech-tree --output docs/assets/tech-tree.svg

  Generate from YAML definition:
    %(prog)s generate --input diagram.yaml --output diagram.svg

  List available components:
    %(prog)s components --list
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # from-system command
    sys_parser = subparsers.add_parser("from-system", help="Generate from current system state")
    sys_parser.add_argument("--output", "-o", required=True, help="Output SVG file path")
    sys_parser.add_argument("--theme", default="blueprint", choices=["blueprint", "dark", "light"])
    sys_parser.add_argument("--format", default="svg", choices=["svg", "html"])

    # from-tech-tree command
    tree_parser = subparsers.add_parser("from-tech-tree", help="Generate from tech tree JSON")
    tree_parser.add_argument("--output", "-o", required=True, help="Output SVG file path")
    tree_parser.add_argument("--input", "-i", default=".slate_tech_tree/tech_tree.json", help="Tech tree JSON path")
    tree_parser.add_argument("--theme", default="blueprint", choices=["blueprint", "dark", "light"])

    # generate command
    gen_parser = subparsers.add_parser("generate", help="Generate from YAML/JSON definition")
    gen_parser.add_argument("--input", "-i", required=True, help="Input YAML/JSON file")
    gen_parser.add_argument("--output", "-o", required=True, help="Output SVG file path")
    gen_parser.add_argument("--theme", default="blueprint", choices=["blueprint", "dark", "light"])
    gen_parser.add_argument("--layout", default="hierarchical", choices=["hierarchical", "force", "grid"])

    # components command
    comp_parser = subparsers.add_parser("components", help="List available components")
    comp_parser.add_argument("--list", "-l", action="store_true", help="List all components")
    comp_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # validate command
    val_parser = subparsers.add_parser("validate", help="Validate definition file")
    val_parser.add_argument("--input", "-i", required=True, help="Input file to validate")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "from-system":
            return cmd_from_system(args)
        elif args.command == "from-tech-tree":
            return cmd_from_tech_tree(args)
        elif args.command == "generate":
            return cmd_generate(args)
        elif args.command == "components":
            return cmd_components(args)
        elif args.command == "validate":
            return cmd_validate(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def cmd_from_system(args) -> int:
    """Generate diagram from current system state."""
    from slate.schematic_sdk import generate_from_system_state, SchematicEngine, SchematicConfig

    print(f"Generating system diagram...")

    svg = generate_from_system_state()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "html":
        config = SchematicConfig(title="SLATE System Architecture")
        engine = SchematicEngine(config)
        html_content = engine._wrap_in_html(svg)
        output_path.write_text(html_content, encoding="utf-8")
    else:
        output_path.write_text(svg, encoding="utf-8")

    print(f"Saved to: {output_path}")
    return 0


def cmd_from_tech_tree(args) -> int:
    """Generate diagram from tech tree JSON."""
    from slate.schematic_sdk import generate_from_tech_tree

    print(f"Generating tech tree diagram from: {args.input}")

    svg = generate_from_tech_tree(args.input)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")

    print(f"Saved to: {output_path}")
    return 0


def cmd_generate(args) -> int:
    """Generate diagram from YAML/JSON definition."""
    from slate.schematic_sdk import SchematicEngine

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    print(f"Generating diagram from: {input_path}")

    # Load definition
    content = input_path.read_text(encoding="utf-8")

    if input_path.suffix in (".yaml", ".yml"):
        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            print("Error: PyYAML not installed. Use JSON format or install pyyaml.", file=sys.stderr)
            return 1
    else:
        data = json.loads(content)

    # Apply CLI overrides
    if "config" not in data:
        data["config"] = {}
    data["config"]["theme"] = args.theme
    data["config"]["layout"] = args.layout

    # Generate
    engine = SchematicEngine.from_dict(data)
    svg = engine.render_svg()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")

    print(f"Saved to: {output_path}")
    return 0


def cmd_components(args) -> int:
    """List available components."""
    components = {
        "nodes": {
            "ServiceNode": "Microservice/server (rounded rectangle)",
            "DatabaseNode": "Data store (cylinder shape)",
            "GPUNode": "GPU/compute resource (hexagon)",
            "AINode": "AI/ML service (rounded rect + brain)",
            "APINode": "API endpoint (rectangle + port)",
            "QueueNode": "Message queue (parallelogram)",
            "ExternalNode": "External service (dashed border)",
        },
        "connections": {
            "FlowConnector": "Data flow with arrow (solid line)",
            "DashedConnector": "Optional/async flow (dashed line)",
            "DataBus": "Multi-connection bus (thick line)",
        },
        "terminals": {
            "InputTerminal": "External input (circle + inward arrow)",
            "OutputTerminal": "External output (circle + outward arrow)",
        },
        "layouts": {
            "hierarchical": "Layer-based arrangement (best for architectures)",
            "force": "Physics-based placement (best for networks)",
            "grid": "Grid snap placement (best for dashboards)",
        },
        "themes": {
            "blueprint": "Dark engineering blueprint (default)",
            "dark": "Dark mode with earth tones",
            "light": "Light mode for presentations",
        }
    }

    if args.json:
        print(json.dumps(components, indent=2))
    else:
        print("\nSLATE Schematic SDK - Available Components\n")
        print("=" * 50)

        for category, items in components.items():
            print(f"\n{category.upper()}:")
            for name, desc in items.items():
                print(f"  {name:20} - {desc}")

    return 0


def cmd_validate(args) -> int:
    """Validate a definition file."""
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        return 1

    print(f"Validating: {input_path}")

    content = input_path.read_text(encoding="utf-8")

    try:
        if input_path.suffix in (".yaml", ".yml"):
            import yaml
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)
    except Exception as e:
        print(f"Parse error: {e}", file=sys.stderr)
        return 1

    errors = []

    # Check required fields
    if "components" not in data and "nodes" not in data:
        errors.append("Missing 'components' or 'nodes' field")

    # Check components have required fields
    for i, comp in enumerate(data.get("components", data.get("nodes", []))):
        if "id" not in comp:
            errors.append(f"Component {i}: missing 'id' field")
        if "label" not in comp:
            errors.append(f"Component {i}: missing 'label' field")

    # Check connections reference valid nodes
    node_ids = {c.get("id") for c in data.get("components", data.get("nodes", []))}
    for i, conn in enumerate(data.get("connections", [])):
        if conn.get("from_node") not in node_ids and conn.get("from") not in node_ids:
            errors.append(f"Connection {i}: invalid 'from' node")
        if conn.get("to_node") not in node_ids and conn.get("to") not in node_ids:
            errors.append(f"Connection {i}: invalid 'to' node")

    if errors:
        print("\nValidation FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\nValidation PASSED")
    print(f"  Components: {len(data.get('components', data.get('nodes', [])))}")
    print(f"  Connections: {len(data.get('connections', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
