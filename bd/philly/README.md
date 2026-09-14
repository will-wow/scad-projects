# USS Philadelphia (1776)

A 3D-printable model of the Continental gunboat USS Philadelphia, built with
[build123d](https://build123d.readthedocs.io/).

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14 (uv will fetch it).

```sh
uv sync
```

## Viewing

Models are previewed with [OCP CAD Viewer](https://github.com/bernhard-42/vscode-ocp-cad-viewer).
Install the `bernhard-42.vscode-ocp-cad-viewer` extension in VS Code, open the
**OCP CAD Viewer** panel, then run:

```sh
uv run main.py
```

`main.py` renders a cube as a hello world.
