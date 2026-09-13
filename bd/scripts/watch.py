"""Re-run a build123d model on every save, without re-paying the import cost.

`import build123d` takes 4-15s; building the model takes ~0.15s. This keeps one
warm process alive and re-executes the model file on change, so iteration is
bounded by the geometry, not the import.

Usage:  uv run python scripts/watch.py [model.py]
Needs the viewer running in another terminal:  just viewer
"""

import os
import pathlib
import sys
import time
import traceback

POLL_SECONDS = 0.25
DEBOUNCE_SECONDS = 0.05
ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {".venv", ".git", "__pycache__", "node_modules"}


def preload() -> float:
    """Import the expensive modules once, up front."""
    start = time.perf_counter()
    import build123d  # noqa: F401  (warming sys.modules is the point)
    import ocp_vscode  # noqa: F401

    return time.perf_counter() - start


def watched_files() -> dict[pathlib.Path, float]:
    """Every project .py file, with its mtime.

    Prunes the virtualenv and friends during the walk; filtering after rglob
    still stats thousands of site-packages files and takes most of a second.
    """
    found = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = pathlib.Path(dirpath, filename)
            try:
                found[path] = path.stat().st_mtime
            except OSError:
                continue
    return found


def purge_local_modules() -> None:
    """Drop project modules from the import cache so edits to them take effect.

    build123d and friends stay loaded; only first-party code is re-imported.
    """
    for name, module in list(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        if not filename or name == "__main__":
            continue
        path = pathlib.Path(filename)
        if ".venv" in path.parts or "site-packages" in path.parts:
            continue
        if path.is_relative_to(ROOT):
            del sys.modules[name]


def run_model(target: pathlib.Path) -> None:
    """Execute the model file, reporting failures without killing the watcher."""
    purge_local_modules()
    namespace = {"__name__": "__main__", "__file__": str(target)}
    start = time.perf_counter()
    try:
        source = target.read_text(encoding="utf-8")
        code = compile(source, str(target), "exec")
    except SyntaxError as err:
        print(f"  syntax error: {err.filename}:{err.lineno}: {err.msg}", flush=True)
        return
    except OSError as err:
        print(f"  could not read {target.name}: {err}", flush=True)
        return

    try:
        exec(code, namespace)  # noqa: S102  (executing the user's own model)
    except Exception as err:  # noqa: BLE001  (any model error must not stop the loop)
        # Skip this function's own frame so the traceback starts in the model.
        tb = err.__traceback__.tb_next if err.__traceback__ else None
        traceback.print_exception(type(err), err, tb)
        return

    print(f"  ok  {time.perf_counter() - start:.2f}s", flush=True)


def main() -> int:
    target = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "main.py").resolve()
    if not target.exists():
        print(f"no such file: {target}")
        return 1

    print("loading build123d ...", flush=True)
    print(f"ready in {preload():.1f}s - watching {target.name}, ctrl-c to stop", flush=True)

    run_model(target)
    seen = watched_files()

    while True:
        time.sleep(POLL_SECONDS)
        current = watched_files()
        changed = [p for p, m in current.items() if seen.get(p) != m]
        if not changed:
            continue
        # Let the editor finish writing before reading.
        time.sleep(DEBOUNCE_SECONDS)
        seen = watched_files()
        names = ", ".join(p.name for p in changed)
        print(f"{time.strftime('%H:%M:%S')}  {names}", flush=True)
        run_model(target)
        saved_at = max(seen.get(p, 0.0) for p in changed)
        print(f"  save -> sent to viewer  {time.time() - saved_at:.2f}s", flush=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nstopped")
