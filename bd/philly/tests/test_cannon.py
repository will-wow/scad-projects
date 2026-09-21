"""The gun.

It prints standing on its muzzle, so most of what can go wrong is about that:
an underside the printer can't bridge, or a bore that doesn't open onto the bed.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from build123d import Vector

from cannon.cannon import CannonSpec, Ring, cannon

SPEC = CannonSpec()


@pytest.fixture(scope="module")
def gun():
    return cannon(SPEC)


def test_it_is_one_valid_solid(gun):
    assert gun.is_valid
    assert len(gun.solids()) == 1


def test_it_is_the_right_size(gun):
    box = gun.bounding_box()
    # The muzzle face is on the bed, and the cascabel adds to the nominal length.
    assert abs(box.min.Z) < 1e-6
    barrel = SPEC.length * SPEC.scale
    assert barrel < box.size.Z < barrel + 3 * SPEC.calibre * SPEC.scale
    # Widest at the base ring: the breech plus the ring standing proud of it.
    widest = (SPEC.breech + 2 * SPEC.base_ring) * SPEC.calibre * SPEC.scale
    assert abs(box.size.X - widest) < 0.02 * widest


def test_the_bore_opens_onto_the_muzzle_face_and_stops_short_of_the_breech(gun):
    bore = SPEC.calibre * SPEC.scale
    wall = (SPEC.neck - 1) / 2 * bore
    assert not gun.is_inside(Vector(0, 0, 0.01)), "the bore should be open at the muzzle"
    assert gun.is_inside(Vector(bore / 2 + wall / 2, 0, 0.01)), "metal round the bore"
    top = (SPEC.length - SPEC.bore_depth * SPEC.calibre) * SPEC.scale
    assert not gun.is_inside(Vector(0, 0, top - bore)), "the bore runs most of the length"
    assert gun.is_inside(Vector(0, 0, top + 0.1)), "the breech is closed"


@pytest.mark.parametrize("overhang", [45.0, 35.0])
def test_nothing_overhangs_more_than_allowed(overhang):
    """Every surface that looks down, other than the one on the bed, is within the limit.

    Checked against the exact surfaces rather than a mesh: a tessellated cone's
    flat facets lean a little steeper than the cone does, which would fail a
    chamfer drawn at exactly the limit. The samples stay off the edges of each
    face's parameter range, where a sphere's pole has no well-defined normal.
    """
    gun = cannon(CannonSpec(max_overhang=overhang))
    samples = np.linspace(0.02, 0.98, 25)
    steepest = max(
        -face.normal_at(u, v).Z
        for face in gun.faces()
        for u in samples
        for v in samples
        if face.position_at(u, v).Z > 1e-6
    )
    # A face leaning `overhang` degrees from vertical has a normal sin(overhang) below level.
    assert steepest <= math.sin(math.radians(overhang)) + 1e-6


def test_the_rings_stand_proud_where_they_are_put():
    spec = CannonSpec(rings=(Ring(at=0.5, proud=0.5),))
    gun = cannon(spec)
    z = 0.5 * spec.length * spec.scale
    barrel = (spec.neck + spec.breech) / 4 * spec.calibre * spec.scale
    assert gun.is_inside(Vector(barrel + 0.4 * spec.calibre * spec.scale, 0, z))
    assert not gun.is_inside(Vector(barrel + 0.4 * spec.calibre * spec.scale, 0, z * 0.9))
