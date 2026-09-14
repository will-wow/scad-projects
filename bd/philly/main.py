"""Hello world for the USS Philadelphia (1776) build123d project.

Renders a cube and shows it in the OCP CAD Viewer. Run with:

    uv run main.py

With the VS Code extension `bernhard-42.vscode-ocp-cad-viewer` installed,
open the "OCP CAD Viewer" panel first so the model has somewhere to land.
"""

from build123d import Box, Part
from ocp_vscode import show_object


def cube(size: float = 20.0) -> Part:
    """A simple cube, centered on the origin."""
    return Box(size, size, size)


def main() -> None:
    result = cube()
    print(f"Cube volume: {result.volume:.1f} mm^3")
    show_object(result, name="cube")


if __name__ == "__main__":
    main()
