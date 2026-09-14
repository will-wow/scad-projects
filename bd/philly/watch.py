"""Live-reload watcher for build123d models.

Importing build123d costs ~16s cold (a few seconds warm), which is what makes
the naive `uv run main.py` edit loop painful. This script pays that cost once,
then keeps the interpreter warm and re-executes only the model file whenever it
changes, pushing the result straight to an already-running OCP CAD Viewer. That
takes the save -> repaint cycle down to about 0.2s.

Usage:
    uv run watch.py [model.py ...] [--port 3939]

Start the viewer first (`just viewer`, or the VS Code OCP CAD Viewer panel).
The watched file is executed exactly as `python <file>` would execute it --
`__name__` is "__main__", so its own `if __name__ == "__main__":` block runs and
calls `show`/`show_object` itself. No special API in the model file.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

# Imported once, up front: this is the expensive part we are amortizing.
import build123d  # noqa: F401  (warms the module cache for the model file)
from ocp_vscode import Camera, reset_show, set_defaults, set_port
from watchfiles import watch

_COLOR = sys.stdout.isatty()
RESET = "\033[0m" if _COLOR else ""
DIM = "\033[2m" if _COLOR else ""
RED = "\033[31m" if _COLOR else ""
GREEN = "\033[32m" if _COLOR else ""


def forget_local_modules(directories: set[Path]) -> None:
    """Drop this project's own modules from the import cache.

    Without this, a model split across files would go stale: editing `hull.py`
    would change nothing, because `import hull` from the model file hands back
    the copy cached on first import. Only modules living in the watched
    directories are dropped, so build123d and the rest of site-packages -- the
    expensive imports -- stay resident.
    """
    for name, module in list(sys.modules.items()):
        if name == "__main__":
            continue  # that's this watcher, which lives in the watched directory
        origin = getattr(module, "__file__", None)
        if origin and Path(origin).resolve().parent in directories:
            del sys.modules[name]


def run_once(path: Path, directories: set[Path]) -> bool:
    """Execute `path` in a fresh namespace, as if it were run as a script.

    Returns True if it ran cleanly. Exceptions are reported and swallowed so a
    typo doesn't kill the watcher mid-session.
    """
    namespace = {
        "__name__": "__main__",
        "__file__": str(path),
        "__builtins__": __builtins__,
    }
    started = time.perf_counter()
    try:
        forget_local_modules(directories)
        code = compile(path.read_text(), str(path), "exec")
        exec(code, namespace)  # noqa: S102  (executing the user's own model)
    except Exception:  # noqa: BLE001  (any model error should be survivable)
        print(f"{RED}--- {path.name} failed ---{RESET}", file=sys.stderr)
        traceback.print_exc()
        return False

    elapsed = time.perf_counter() - started
    print(f"{GREEN}reloaded{RESET} {path.name} {DIM}({elapsed:.2f}s){RESET}", flush=True)
    return True


def run_all(files: list[Path], directories: set[Path]) -> None:
    """Re-render the whole watched set as one scene.

    `show_object` accumulates into a module-level stack inside ocp_vscode and
    only ever appends, so without this reset the viewer would keep every shape
    from every previous reload: shrinking a sphere would draw the small one
    inside the stale big one, and deleting it would change nothing at all. The
    reset is per batch rather than per file so that watching several model files
    still composes them into a single scene.
    """
    reset_show()
    for file in files:
        run_once(file, directories)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "files",
        nargs="*",
        default=["main.py"],
        type=Path,
        help="model files to watch and re-run (default: main.py)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3939,
        help="port the OCP CAD Viewer is listening on (default: 3939)",
    )
    args = parser.parse_args()

    files = [Path(f) for f in args.files]
    missing = [f for f in files if not f.is_file()]
    if missing:
        print(f"no such file: {', '.join(str(m) for m in missing)}", file=sys.stderr)
        return 1

    targets = {f.resolve(): f for f in files}
    # Watch the containing directories, not the files themselves. Most editors
    # (vim, and VS Code's atomic save) write a temp file and rename it over the
    # original, which replaces the inode -- a watch on the file itself goes deaf
    # after the first save. A directory watch survives that.
    directories = {f.parent for f in targets}

    # So a model file can import its siblings (`from hull import hull`).
    for directory in directories:
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))

    set_port(args.port)
    # Without this the camera snaps back to the default view on every reload,
    # which makes a live loop useless -- you lose your vantage point each save.
    set_defaults(reset_camera=Camera.KEEP)

    watched = ", ".join(f.name for f in files)
    print(f"{DIM}watching {watched} -> viewer on port {args.port} (ctrl-c to stop){RESET}")

    run_all(files, directories)

    # step/debounce keep the save -> repaint latency low; watchfiles coalesces
    # the several events an editor emits for one save into a single batch.
    this_file = Path(__file__).resolve()
    try:
        for changes in watch(*directories, step=10, debounce=100):
            touched = {Path(path).resolve() for _, path in changes}
            # Any .py in the watched directories re-runs the targets, not just
            # the targets themselves: a model split across files is still one
            # model, so editing hull.py should repaint the ship too.
            if not any(
                p.suffix == ".py" and p != this_file and p.parent in directories
                for p in touched
            ):
                continue
            run_all(list(targets.values()), directories)
    except KeyboardInterrupt:
        print(f"{DIM}stopped{RESET}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
