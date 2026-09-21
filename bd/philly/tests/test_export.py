"""What goes to the slicer.

A mesh that a slicer offers to "repair" is a mesh nobody should have shipped,
so the export asserts its own output is manifold; these check that the
assertion means something and that the file says what it should.
"""

from __future__ import annotations

import numpy as np
import pytest
from build123d import Box

from export import weld, write_3mf


def test_welding_joins_coincident_vertices():
    """OCCT tessellates each face alone, so a shared edge arrives twice."""
    points = np.array([[0.0, 0, 0], [1, 0, 0], [0, 1, 0], [0.0, 0, 0], [1, 0, 0], [1, 1, 0]])
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    welded, remapped = weld(points, faces)
    assert len(welded) == 4, "the two copies of each shared vertex should merge"
    assert len(remapped) == 2, "both triangles still have area"


def test_welding_drops_triangles_that_collapse():
    points = np.array([[0.0, 0, 0], [1, 0, 0], [1.0, 0, 0], [0, 1, 0]])
    faces = np.array([[0, 1, 2], [0, 1, 3]])  # the first is a sliver once welded
    _, remapped = weld(points, faces)
    assert len(remapped) == 1


def test_a_box_exports_as_a_manifold_3mf(tmp_path):
    lib3mf = pytest.importorskip("lib3mf")
    path = tmp_path / "box.3mf"
    points, faces = write_3mf(Box(10, 20, 30), path)
    assert path.exists() and path.stat().st_size > 0
    assert points == 8, "a welded box has eight corners, not twenty-four"
    assert faces == 12

    model = lib3mf.get_wrapper().CreateModel()
    model.QueryReader("3mf").ReadFromFile(str(path))
    assert model.GetUnit() == lib3mf.ModelUnit.MilliMeter, "a slicer should not have to guess"
    meshes = model.GetMeshObjects()
    assert meshes.MoveNext()
    mesh = meshes.GetCurrentMeshObject()
    assert mesh.IsManifoldAndOriented()
    assert mesh.GetTriangleCount() == 12


def test_the_hull_exports_as_a_manifold_3mf(decked_hull, tmp_path):
    lib3mf = pytest.importorskip("lib3mf")
    path = tmp_path / "hull.3mf"
    points, faces = write_3mf(decked_hull, path)
    assert points > 100 and faces > 100

    model = lib3mf.get_wrapper().CreateModel()
    model.QueryReader("3mf").ReadFromFile(str(path))
    meshes = model.GetMeshObjects()
    assert meshes.MoveNext()
    assert meshes.GetCurrentMeshObject().IsManifoldAndOriented()
