"""The gun.

It prints standing on its muzzle, so most of what can go wrong is about that:
an underside the printer can't bridge, or a bore that doesn't open onto the bed.
"""

from __future__ import annotations

import math

import pytest
from build123d import Vector
from conftest import steepest_overhang

from cannon.cannon import CannonSpec, Ring, cannon, trunnion_height

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


def test_the_bore_opens_onto_the_muzzle_face_and_stops_short_of_the_trunnions(gun):
    """The trunnions must bear on solid metal, so the bore is a muzzle detail only."""
    bore = SPEC.calibre * SPEC.scale
    wall = (SPEC.neck - 1) / 2 * bore
    assert not gun.is_inside(Vector(0, 0, 0.01)), "the bore should be open at the muzzle"
    assert gun.is_inside(Vector(bore / 2 + wall / 2, 0, 0.01)), "metal round the bore"
    top = SPEC.bore_length * bore
    assert not gun.is_inside(Vector(0, 0, top - bore)), "the bore runs its stated length"
    assert gun.is_inside(Vector(0, 0, top + 0.1)), "and is closed above that"
    assert gun.is_inside(Vector(0, 0, trunnion_height(SPEC))), "solid at the trunnions"


@pytest.mark.parametrize("overhang", [45.0, 35.0])
def test_nothing_overhangs_more_than_allowed(overhang):
    """The rings, the button and the roof of each trunnion socket, all as printed."""
    gun = cannon(CannonSpec(max_overhang=overhang))
    assert steepest_overhang(gun) <= math.sin(math.radians(overhang)) + 1e-6


def test_the_rings_stand_proud_where_they_are_put():
    spec = CannonSpec(rings=(Ring(at=0.5, proud=0.5),))
    gun = cannon(spec)
    z = 0.5 * spec.length * spec.scale
    barrel = (spec.neck + spec.breech) / 4 * spec.calibre * spec.scale
    assert gun.is_inside(Vector(barrel + 0.4 * spec.calibre * spec.scale, 0, z))
    assert not gun.is_inside(Vector(barrel + 0.4 * spec.calibre * spec.scale, 0, z * 0.9))
