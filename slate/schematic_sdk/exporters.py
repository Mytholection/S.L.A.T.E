#!/usr/bin/env python3
# Modified: 2026-02-08T01:15:00Z | Author: COPILOT | Change: Create schematic SDK export handlers
"""
SLATE Schematic SDK - Export Handlers

Provides export functionality for SVG diagrams to various formats
and targets (file, HTML wrapper, base64, JSON manifest).
"""

import base64
import json
from pathlib import Path
from typing import Any, Dict, Optional


class SVGExporter:
    """Export SVG to file."""

    @staticmethod
    def to_file(svg_content: str, path: str) -> Path:
        """
        Save SVG content to a file.

        Args:
            svg_content: SVG string to save
            path: Output file path

        Returns:
            Path to the saved file
        """
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(svg_content, encoding="utf-8")
        return output


class HTMLExporter:
    """Export SVG wrapped in an HTML document."""

    @staticmethod
    def to_file(
        svg_content: str,
        path: str,
        title: str = "SLATE Schematic",
        background: str = "#0D1B2A",
    ) -> Path:
        """
        Save SVG wrapped in HTML to a file.

        Args:
            svg_content: SVG string
            path: Output file path
            title: HTML page title
            background: Page background color

        Returns:
            Path to the saved file
        """
        html_content = HTMLExporter.wrap(svg_content, title, background)
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html_content, encoding="utf-8")
        return output

    @staticmethod
    def wrap(
        svg_content: str,
        title: str = "SLATE Schematic",
        background: str = "#0D1B2A",
    ) -> str:
        """
        Wrap SVG in a standalone HTML document.

        Args:
            svg_content: SVG string
            title: HTML page title
            background: Page background color

        Returns:
            HTML string
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            background: {background};
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        svg {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }}
    </style>
</head>
<body>
{svg_content}
</body>
</html>"""


class Base64Exporter:
    """Export SVG as base64-encoded data URI."""

    @staticmethod
    def encode(svg_content: str) -> str:
        """
        Encode SVG as a base64 data URI.

        Args:
            svg_content: SVG string

        Returns:
            Data URI string (data:image/svg+xml;base64,...)
        """
        encoded = base64.b64encode(svg_content.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"

    @staticmethod
    def to_img_tag(svg_content: str, alt: str = "SLATE Schematic") -> str:
        """
        Create an HTML img tag with base64-encoded SVG.

        Args:
            svg_content: SVG string
            alt: Alt text for the image

        Returns:
            HTML img tag string
        """
        data_uri = Base64Exporter.encode(svg_content)
        return f'<img src="{data_uri}" alt="{alt}" />'


class MarkdownExporter:
    """Export SVG for Markdown documents."""

    @staticmethod
    def to_inline(svg_content: str) -> str:
        """
        Format SVG for inline Markdown embedding.

        Args:
            svg_content: SVG string

        Returns:
            SVG wrapped for Markdown compatibility
        """
        # Strip XML declaration for inline use
        content = svg_content
        if content.startswith("<?xml"):
            content = content[content.index("?>") + 2 :].strip()
        return content

    @staticmethod
    def to_link(
        svg_path: str, alt: str = "SLATE System Diagram", title: str = ""
    ) -> str:
        """
        Create a Markdown image link.

        Args:
            svg_path: Relative path to SVG file
            alt: Alt text
            title: Optional title text

        Returns:
            Markdown image syntax
        """
        if title:
            return f'![{alt}]({svg_path} "{title}")'
        return f"![{alt}]({svg_path})"


class JSONExporter:
    """Export diagram definition as JSON manifest."""

    @staticmethod
    def to_manifest(
        svg_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a JSON manifest with SVG content and metadata.

        Args:
            svg_content: SVG string
            metadata: Optional metadata dict

        Returns:
            JSON string
        """
        manifest = {
            "format": "svg",
            "version": "1.0.0",
            "sdk": "slate-schematic-sdk",
            "svg_length": len(svg_content),
            "metadata": metadata or {},
            "content": svg_content,
        }
        return json.dumps(manifest, indent=2)

    @staticmethod
    def to_file(
        svg_content: str,
        path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Save JSON manifest to file.

        Args:
            svg_content: SVG string
            path: Output file path
            metadata: Optional metadata

        Returns:
            Path to saved file
        """
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            JSONExporter.to_manifest(svg_content, metadata), encoding="utf-8"
        )
        return output
