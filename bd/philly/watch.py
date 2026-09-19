"""Live-reload watcher for build123d models.

Importing build123d costs 15-25s cold (a few seconds warm), which is what makes
the naive `uv run main.py` edit loop painful. This script pays that cost once,
then keeps the interpreter warm and re-executes only the model file whenever it
changes, pushing the result straight to an already-running OCP CAD Viewer. That
puts the save -> repaint cycle at roughly the cost of the geometry itself.

Usage:
    uv run watch.py [model.py ...] [--port 3939]

Start the viewer first (`just viewer`, or the VS Code OCP CAD Viewer panel).
The watched file is executed exactly as `python <file>` would execute it --
`__name__` is "__main__", so its own `if __name__ == "__main__":` block runs and
calls `show`/`show_all`/`show_object` itself. No special API in the model file.
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

from watchfiles import watch

_COLOR = sys.stdout.isatty()
RESET = "\033[0m" if _COLOR else ""
DIM = "\033[2m" if _COLOR else ""
RED = "\033[31m" if _COLOR else ""
GREEN = "\033[32m" if _COLOR else ""

# Directories whose modules must stay resident -- these are the expensive imports.
VENDORED = (f"{os.sep}.venv{os.sep}", f"{os.sep}site-packages{os.sep}")
VENDORED_DIRS = {".venv", "site-packages"}


def preload() -> float:
    """Import the expensive modules once, up front. Returns seconds taken."""
    started = time.perf_counter()
    import build123d  # noqa: F401  (warming sys.modules is the point)
    import ocp_vscode  # noqa: F401

    return time.perf_counter() - started


def drop_bytecode_caches(roots: set[Path]) -> None:
    """Stop Python serving stale bytecode for first-party modules.

    A .pyc is considered current when its recorded source mtime (whole seconds)
    and size match the .py. Two edits in the same second that don't change the
    file's length -- `Box(13, 13, 13)` to `Box(15, 15, 15)`, exactly the kind of
    tweak this loop exists for -- collide on both, so a re-import silently hands
    back the previous bytecode and the viewer shows the old geometry.

    Writing no new caches makes every reload compile from source; clearing the
    ones already on disk covers those a plain `just run` left behind.
    """
    sys.dont_write_bytecode = True
    for root in roots:
        for cache in root.rglob("__pycache__"):
            if any(part in VENDORED_DIRS for part in cache.parts):
                continue
            shutil.rmtree(cache, ignore_errors=True)


def forget_local_modules(prefixes: tuple[str, ...]) -> None:
    """Drop this project's own modules from the import cache.

    Without this, a model split across files goes stale: editing `hull.py`
    changes nothing, because `import hull` hands back the copy cached on first
    import. Only first-party modules under the watched roots are dropped, so
    build123d and the rest of site-packages stay loaded.

    This runs on every reload against the whole module table (~3000 entries once
    build123d is in), so it matches on strings. Building a Path and calling
    .resolve() per module costs ~73ms a reload -- comparable to the geometry it
    is meant to be getting out of the way of -- against ~1ms for this.
    """
    for name, module in list(sys.modules.items()):
        if name == "__main__":
            continue  # that's this watcher, which lives under a watched root
        origin = getattr(module, "__file__", None)
        if not origin or not origin.startswith(prefixes):
            continue
        if any(vendored in origin for vendored in VENDORED):
            continue
        del sys.modules[name]
    # So a module added since startup is found rather than reported missing.
    importlib.invalidate_caches()


def run_once(path: Path, prefixes: tuple[str, ...]) -> bool:
    """Execute `path` in a fresh namespace, as if it were run as a script.

    Returns True if it ran cleanly. Failures are reported and swallowed so a
    typo doesn't kill the watcher mid-session.
    """
    forget_local_modules(prefixes)
    namespace = {
        "__name__": "__main__",
        "__file__": str(path),
        "__builtins__": __builtins__,
    }
    started = time.perf_counter()

    try:
        code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    except SyntaxError as err:
        # A one-liner beats a traceback here: the location is the whole message.
        print(f"{RED}{err.filename}:{err.lineno}: {err.msg}{RESET}", flush=True)
        return False
    except OSError as err:
        print(f"{RED}could not read {path.name}: {err}{RESET}", flush=True)
        return False

    try:
        exec(code, namespace)  # noqa: S102  (executing the user's own model)
    except Exception as err:  # noqa: BLE001  (any model error must not stop the loop)
        print(f"{RED}--- {path.name} failed ---{RESET}", file=sys.stderr)
        # Drop this function's own frame so the traceback starts in the model.
        tb = err.__traceback__.tb_next if err.__traceback__ else None
        traceback.print_exception(type(err), err, tb)
        return False

    elapsed = time.perf_counter() - started
    print(f"{GREEN}reloaded{RESET} {path.name} {DIM}({elapsed:.2f}s){RESET}", flush=True)
    return True


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
    if missing := [f for f in files if not f.is_file()]:
        print(f"no such file: {', '.join(str(m) for m in missing)}", file=sys.stderr)
        return 1

    targets = {f.resolve(): f for f in files}
    # Watch the containing directories, not the files themselves. Most editors
    # (vim, and VS Code's atomic save) write a temp file and rename it over the
    # original, which replaces the inode -- a watch on the file itself goes deaf
    # after the first save. A directory watch survives that, and watchfiles
    # recurses, so models split into subpackages are covered too.
    roots = {f.parent for f in targets}

    # Matched as strings by forget_local_modules; trailing separator so that a
    # sibling directory sharing a name prefix can't match.
    prefixes = tuple(f"{root}{os.sep}" for root in roots)

    # So a model file can import its siblings (`from hull import hull`).
    for root in roots:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

    drop_bytecode_caches(roots)

    print("loading build123d ...", flush=True)
    seconds = preload()

    # Imported here: preload() has already paid for it.
    from ocp_vscode import Camera, set_defaults, set_port

    set_port(args.port)
    # Without this the camera snaps back to the default view on every reload,
    # which makes a live loop useless -- you lose your vantage point each save.
    set_defaults(reset_camera=Camera.KEEP)

    watched = ", ".join(f.name for f in files)
    print(
        f"{DIM}ready in {seconds:.1f}s - watching {watched} "
        f"-> viewer on port {args.port}, ctrl-c to stop{RESET}",
        flush=True,
    )

    for file in files:
        run_once(file, prefixes)

    this_file = Path(__file__).resolve()
    # step/debounce keep the save -> repaint latency low (~16ms of notification
    # overhead, measured) while still coalescing the several events an editor
    # emits for one save into a single batch. watchfiles' default filter already
    # ignores .venv, .git and __pycache__.
    for changes in watch(*roots, step=10, debounce=100):
        touched = {Path(path).resolve() for _, path in changes}
        # Any .py under the watched roots re-runs the targets, not just the
        # targets themselves: a model split across files is still one model.
        if not any(
            p.suffix == ".py" and p != this_file and any(p.is_relative_to(r) for r in roots)
            for p in touched
        ):
            continue
        for file in targets.values():
            run_once(file, prefixes)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print(f"\n{DIM}stopped{RESET}")
