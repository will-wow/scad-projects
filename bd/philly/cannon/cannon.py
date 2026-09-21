"""The gun itself: a smoothbore muzzle-loader, turned as one solid of revolution.

    just watch cannon/cannon.py     # preview it on its own

Parts are named as an 18th-century gunfounder would, muzzle to breech:

    muzzle face    the flat front end, round the mouth of the bore
    swell of the muzzle
                   the flare at the front end; its hollow curve is the cavetto
    neck           the narrowest part of the piece, just behind the swell
    muzzle astragal
                   the first raised ring behind the neck
    chase          the long forward part, from the neck back to the reinforces
    second reinforce ring, first reinforce ring
                   rings marking the front of each reinforce: the thicker
                   rear barrel, which takes the force of the charge
    base ring      the ring at the very back of the barrel
    base of the breech
                   the rounded back end behind the base ring
    cascabel       the knob on the back: a short neck carrying the button

A real gun steps out in diameter at each reinforce ring. This one is a single
gentle taper with the rings standing proud of it -- the toy reads the same and
has fewer ledges to print.

Proportions are in calibres (bore diameters), the way the founders' own rules
were written, so the whole gun follows from `length` and `calibre`. The
defaults are the 12-pounder in the bow; the 9-pounders are the same shape at a
smaller calibre.

The gun is built in its print orientation: muzzle face down on the bed at the
origin, bore along +Z. Nothing on the outside overhangs more than
`max_overhang`, so it prints standing on its muzzle with a brim and no support.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from build123d import (
    Align,
    Axis,
    BuildLine,
    BuildPart,
    BuildSketch,
    Cone,
    Cylinder,
    Line,
    Locations,
    Mode,
    Part,
    Plane,
    Polyline,
    SagittaArc,
    ThreePointArc,
    make_face,
    revolve,
    scale,
)
from ocp_vscode import show_object


@dataclass(frozen=True)
class Ring:
    """A raised, rounded ring round the barrel -- an astragal or reinforce ring."""

    at: float  # centre, as a fraction of `length` back from the muzzle face
    proud: float  # how far it stands off the barrel, calibres


@dataclass(frozen=True)
class CannonSpec:
    length: float = 2438  # 8ft for the 12 lb cannon, muzzle face to base ring
    calibre: float = 117  # bore diameter: 4.62in for a 12-pounder
    # Printed size over real size. The hull's default prints the 16.4m boat at
    # 300mm, about 1:55; match that so the gun sits on the deck at scale.
    scale: float = 1 / 55

    # Diameters, in calibres.
    swell: float = 2.4  # the swell of the muzzle, at the muzzle face
    neck: float = 2.1
    breech: float = 2.8  # the barrel at the base ring; it tapers to `neck` from here

    # Along the axis, in calibres.
    lip: float = 0.2  # the straight band at the muzzle face, before the swell curves in
    muzzle: float = 1.3  # muzzle face to the neck
    base_of_breech: float = 0.5  # base ring to the cascabel's neck
    cascabel_neck: float = 0.3  # length of the neck carrying the button
    bore_depth: float = 1.0  # solid metal left behind the bottom of the bore

    # The cascabel, as diameters in calibres.
    cascabel_neck_diameter: float = 0.7
    button: float = 1.2

    # Rings along the chase and reinforces. Positions follow the founders'
    # rule of a first reinforce 2/7 of the length and a second 1/7 plus a
    # calibre; the muzzle astragal is eyeballed from the scan.
    rings: tuple[Ring, ...] = (
        Ring(at=0.14, proud=0.15),  # muzzle astragal
        Ring(at=0.52, proud=0.2),  # second reinforce ring
        Ring(at=0.71, proud=0.2),  # first reinforce ring
    )
    base_ring: float = 0.25  # proud, calibres; it sits at the very end of the barrel

    # Steepest the underside of anything may lean, degrees from vertical. The
    # gun prints muzzle-down, so every ring and the button get a straight
    # chamfer underneath instead of the full round.
    max_overhang: float = 45.0


def _teardrop(start: tuple[float, float], radius: float, overhang: float) -> tuple[float, float]:
    """A round moulding that prints without support. Returns the point it ends on.

    Draws into the active BuildLine: a half-round of `radius` standing on the
    line x = start[0], with its underside -- the side facing the bed -- cut off
    as a straight chamfer where the round would get steeper than `overhang`
    degrees from vertical. The chamfer starts at `start`, and the round ends on
    top, back at the same x it started from.
    """
    return _teardrop_onto(start, start[0], radius, overhang)


def _teardrop_onto(
    start: tuple[float, float], cx: float, radius: float, overhang: float
) -> tuple[float, float]:
    """As _teardrop, but the round is centred on x = cx rather than on `start`.

    The cascabel's button needs this: it is centred on the axis, while its
    chamfer starts out on the neck that carries it.
    """
    lean = math.radians(overhang)
    x0, y0 = start
    # The chamfer meets the circle where the circle's own slope matches it.
    tangent_x = cx + radius * math.cos(lean)
    cy = y0 + (tangent_x - x0) / math.tan(lean) + radius * math.sin(lean)
    tangent = (tangent_x, cy - radius * math.sin(lean))
    top = (cx, cy + radius)
    Line(start, tangent)
    ThreePointArc(tangent, (cx + radius, cy), top)
    return top


def cannon(spec: CannonSpec) -> Part:
    cal = spec.calibre
    lean = math.radians(spec.max_overhang)

    # Working in the sketch plane: x is the radius out from the bore's axis and
    # y the height above the muzzle face. Everything is real-world millimetres
    # until the one scale() at the end.
    neck_y = spec.muzzle * cal
    neck_r = spec.neck * cal / 2
    breech_r = spec.breech * cal / 2

    def barrel(y: float) -> float:
        """Radius of the bare barrel (no rings) at height y."""
        return neck_r + (breech_r - neck_r) * (y - neck_y) / (spec.length - neck_y)

    with BuildPart() as gun:
        # Plane.XZ, so the sketch's y is the world's Z: the profile stands up
        # and revolve() spins it round the Z axis.
        with BuildSketch(Plane.XZ):
            with BuildLine():
                # The muzzle face and lip, then the cavetto: the hollow curve of
                # the swell narrowing to the neck. Hollow, so it leans inward
                # going up, and there is nothing here to overhang.
                swell_r = spec.swell * cal / 2
                Polyline((0, 0), (swell_r, 0), (swell_r, spec.lip * cal))
                SagittaArc((swell_r, spec.lip * cal), (neck_r, neck_y), 0.15 * cal)

                # Up the chase and reinforces, ring by ring. `here` is the pen:
                # each segment starts exactly where the last one ended.
                here = (neck_r, neck_y)
                for ring in spec.rings:
                    radius = ring.proud * cal
                    # Start the chamfer low enough that the ring centres on `at`.
                    y = ring.at * spec.length - radius / math.sin(lean)
                    Line(here, (barrel(y), y))
                    here = _teardrop((barrel(y), y), radius, spec.max_overhang)

                # The base ring, whose top is the end of the barrel.
                radius = spec.base_ring * cal
                y = spec.length - radius - radius / math.sin(lean)
                Line(here, (barrel(y), y))
                here = _teardrop((barrel(y), y), radius, spec.max_overhang)

                # The base of the breech, domed, closing in to the cascabel.
                cascabel_r = spec.cascabel_neck_diameter * cal / 2
                breech_top = (cascabel_r, here[1] + spec.base_of_breech * cal)
                SagittaArc(here, breech_top, -0.2 * spec.base_of_breech * cal)

                # The cascabel: its neck, then the button, closing on the axis.
                neck_top = (cascabel_r, breech_top[1] + spec.cascabel_neck * cal)
                Line(breech_top, neck_top)
                here = _teardrop_onto(neck_top, 0, spec.button * cal / 2, spec.max_overhang)

                # And back down the axis to where we started.
                Line(here, (0, 0))
            make_face()
        revolve(axis=Axis.Z)

        # The bore, drilled up from the muzzle face. It ends in a point rather
        # than flat, so its roof prints without bridging.
        bore_r = cal / 2
        point = bore_r / math.tan(lean)
        depth = spec.length - spec.bore_depth * cal - point
        from_the_bed = (Align.CENTER, Align.CENTER, Align.MIN)
        Cylinder(bore_r, depth, align=from_the_bed, mode=Mode.SUBTRACT)
        with Locations((0, 0, depth)):
            Cone(bore_r, 0, point, align=from_the_bed, mode=Mode.SUBTRACT)

        # Last, down to toy size. Everything above is real-world millimetres.
        scale(by=spec.scale)

    assert gun.part is not None, "BuildPart always holds a part once revolve() has run"
    return gun.part


def model() -> Part:
    """The thing to render: `just preview --model cannon.cannon:model` looks for this."""
    return cannon(CannonSpec())


def main() -> None:
    gun = model()
    box = gun.bounding_box().size
    print(f"cannon {box.X:.1f} x {box.Y:.1f} x {box.Z:.1f} mm, {gun.volume:.0f} mm^3 of material")
    show_object(gun, name="cannon")


if __name__ == "__main__":
    main()
