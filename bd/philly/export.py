"""Write the model out as a 3MF, ready for a slicer.

3MF rather than STL: it records the unit, so a slicer knows the model is in
millimetres instead of guessing, and it stores the mesh as indexed vertices
rather than a list of loose triangles.

    just build

build123d has no 3MF writer, but lib3mf -- the 3MF Consortium's own library --
comes along with ocp_vscode, so the mesh goes straight from the tessellation
into that.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import lib3mf
import numpy as np
from build123d import Part, export_step, export_stl

from preview import load_model

# The parts a print needs, as module:callable=label. They are separate files
# rather than one: each wants its own orientation on the bed, and the hull's
# watertightness settings -- three walls, six bottom layers -- are wrong for a
# 0.6mm sail.
PARTS = (
    "main:model=hull",
    "main:mast=mast",
    "main:sails=sails",
    "main:awning=awning",
    "main:canvas=awning-canvas",
    "cannon.cannon:model=gun",
    "cannon.carriage:model=carriage",
    "cannon.cannon:nine_pounder=gun-9",
    "main:broadside_carriage=carriage-9",
    "cannon.trunnion:model=trunnion",
    "cannon.cap_square:model=cap-square",
)

# Tessellation tolerance in millimetres of the finished model. Finer than a
# printer's nozzle, so the mesh is not what limits the print.
MESH_TOLERANCE = 0.05


# Vertices closer together than this are the same vertex. OCCT emits
# coordinates that agree to far better than this along a shared edge.
WELD_TOLERANCE = 1e-6


def weld(points: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Merge coincident vertices and drop the triangles that collapse.

    OCCT tessellates each face on its own, so the two faces meeting along an
    edge each get their own copy of the vertices on it. Nothing is topologically
    joined, and 3MF reports the result as not manifold -- which is the usual
    reason a slicer starts talking about repairing a model. Welding by position
    is enough to close it, since the duplicates are the same point.
    """
    keys = np.round(points / WELD_TOLERANCE).astype(np.int64)
    _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    welded = points[first]
    remapped = inverse[faces]
    # A triangle spanning two vertices that turned out to be one has no area.
    keep = (
        (remapped[:, 0] != remapped[:, 1])
        & (remapped[:, 1] != remapped[:, 2])
        & (remapped[:, 2] != remapped[:, 0])
    )
    return welded, remapped[keep]


def write_3mf(part: Part, path: Path, *, tolerance: float = MESH_TOLERANCE) -> tuple[int, int]:
    """Tessellate `part` and write it to `path`. Returns (vertices, triangles)."""
    raw_vertices, raw_triangles = part.tessellate(tolerance)
    points, faces = weld(
        np.array([[v.X, v.Y, v.Z] for v in raw_vertices], dtype=float),
        np.array(raw_triangles, dtype=np.int64),
    )

    wrapper = lib3mf.get_wrapper()
    model = wrapper.CreateModel()
    if model is None:  # the binding types this optional; it never is in practice
        raise RuntimeError("lib3mf would not create a model")
    # Without this a slicer has to guess the scale, which is the one thing 3MF
    # is meant to settle.
    model.SetUnit(lib3mf.ModelUnit.MilliMeter)

    mesh = model.AddMeshObject()
    mesh.SetName(path.stem)
    mesh.SetGeometry(
        [lib3mf.Position((x, y, z)) for x, y, z in points],
        [lib3mf.Triangle((int(a), int(b), int(c))) for a, b, c in faces],
    )
    model.AddBuildItem(mesh, wrapper.GetIdentityTransform())

    path.parent.mkdir(parents=True, exist_ok=True)
    if not mesh.IsManifoldAndOriented():
        raise RuntimeError(
            "the mesh is not manifold after welding; a slicer would want to repair it"
        )

    model.QueryWriter("3mf").WriteToFile(str(path))
    return len(points), len(faces)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        action="append",
        metavar="MODULE:CALLABLE[=LABEL]",
        help=f"a part to build; repeatable. Default: {' '.join(PARTS)}",
    )
    parser.add_argument(
        "--out", type=Path, default=Path("dist"), help="output directory (default: dist/)"
    )
    parser.add_argument("--name", default="philadelphia", help="base filename")
    parser.add_argument("--stl", action="store_true", help="also write an STL")
    parser.add_argument("--step", action="store_true", help="also write a STEP")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    for target in args.model or PARTS:
        source, _, label = target.partition("=")
        label = label or source.rpartition(":")[2]
        part = load_model(source)
        if not part.is_valid:
            raise SystemExit(f"{source} is not a valid solid; refusing to export it")

        size = part.bounding_box().size
        pieces = len(part.solids())
        print(
            f"{label:6} {size.X:7.1f} x {size.Y:6.1f} x {size.Z:6.1f} mm, "
            f"{part.volume / 1000:6.2f} cm3"
            f"{f', {pieces} pieces' if pieces > 1 else ''}"
        )

        stem = f"{args.name}-{label}"
        points, faces = write_3mf(part, args.out / f"{stem}.3mf")
        print(f"       {args.out / f'{stem}.3mf'}  {points} vertices, {faces} triangles")

        if args.stl:
            export_stl(part, str(args.out / f"{stem}.stl"), tolerance=MESH_TOLERANCE)
        if args.step:
            export_step(part, str(args.out / f"{stem}.step"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
