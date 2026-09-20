# USS Philadelphia (1776)

A 3D-printable model of the Continental gunboat USS Philadelphia, built with
[build123d](https://build123d.readthedocs.io/).

## Setup

Requires [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).
uv will fetch Python 3.14 itself.

```sh
just sync
```

## The edit loop

In one terminal, start the viewer:

```sh
just viewer
```

That runs the standalone [OCP CAD Viewer](https://github.com/bernhard-42/vscode-ocp-cad-viewer)
at <http://127.0.0.1:3939> — open it in a browser. If you'd rather work inside
VS Code, install the `bernhard-42.vscode-ocp-cad-viewer` extension and open its
**OCP CAD Viewer** panel instead; skip `just viewer` in that case.

In a second terminal, start the watcher:

```sh
just watch              # watches main.py
just watch hull.py      # or any other model file(s)
```

Now every save repaints the viewer in about 0.2s.

The speed comes from not restarting Python: importing build123d takes ~16s cold
and a few seconds warm, so `watch.py` pays that once at startup and then only
re-executes the model file on each change. The camera is left where you put it
(`Camera.KEEP`), and a syntax error or a broken model prints a traceback without
killing the watcher — fix the file, save again, and it picks up where it left off.

The watched file is executed exactly as `python <file>` would run it, so it needs
no special API: its own `if __name__ == "__main__":` block runs and calls
`show`/`show_object`. `just run` executes it the slow way, in a fresh process.

Once the model grows past one file, editing any `.py` under the model's
directory — subpackages included — re-renders too. The project's own modules are
dropped from the import cache each reload, so a change to `parts/hull.py` shows
up immediately rather than serving the copy Python cached on first import. The
watcher also disables bytecode caching for itself: a `.pyc` counts as current
when the source's size and whole-second mtime match, so two quick edits of the
same length (`Box(13, 13, 13)` to `Box(15, 15, 15)`) would otherwise re-import
stale bytecode and repaint the *old* geometry.

Each batch resets the viewer's object stack before re-running, since
`show_object` only ever appends to it — otherwise shrinking a shape would draw
the small one inside the stale large one, and deleting one would do nothing.

## The hull

`lines.py` reads `designs/philadelphia_hull_lines.dxf` — a lines plan derived
from the Smithsonian's scan of the surviving boat, at true 1:1 real-world
millimetres — and `hull.py` lofts it into a hollow solid.

The hull is a hard-chine scow, so every transverse section is a trapezoid:
centreline to chine along the flat bottom, then straight out and up to the rail.
The solid is a loft through those sections, hollowed with OCCT's thick-solid
operation with the deck face removed.

Scale and wall thickness live in `HullSpec` (`main.py` sets them). The source
data is the real 16.4m boat; the default prints it at 300mm, or about 1:55.

**The profile curves in the DXF are not hand-faired.** `FAIR_T` and
`FAIR_BOTTOM` — the plan-view sheer and chine — are. The two profile curves are
still raw scan output carrying the artefacts the handoff documents: an 871mm
spike at the bow of `BASE_PROFILE`, a transom that confuses the last stations of
both. `lines.fair()` trims those documented regions by count and smooths the
rest, which is enough for a toy but is not the same as fairing them by eye.

## Recipes

```
just            # list recipes
just sync       # install/refresh the venv from uv.lock
just viewer     # start the browser viewer on port 3939
just watch      # live-reload model files into the viewer
just run        # render once, in a fresh process
just format     # ruff format + fix
just check      # ruff format --check, ruff check, pyright
```
