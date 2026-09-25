"""The cap square: the strap that holds a trunnion in its bed.

On the real gun it is a hinged iron strap dropped over the trunnion and held
by a key. Here it is a small block grooved to match the bracket's rail, which
slides aft over the trunnion and clicks past a detent. Two per gun.

Its outer leg catches under the rail's hook and its inner lip rides the rail's
chamfer, so lifting it only drives it further under the hook. Nothing springs.

It prints groove-up, which is upside down from how it is fitted: that way the
groove narrows as it rises and nothing overhangs.

    just watch cannon/cap_square.py
"""

from __future__ import annotations

from dataclasses import dataclass, field

from build123d import (
    Axis,
    BuildPart,
    BuildSketch,
    Kind,
    Location,
    Mode,
    Part,
    Plane,
    Polygon,
    extrude,
    offset,
)
from ocp_vscode import show_object

from cannon.carriage import CarriageSpec


@dataclass(frozen=True)
class CapSquareSpec:
    carriage: CarriageSpec = field(default_factory=CarriageSpec)

    length: float = 6.1  # along the rail
    wall: float = 0.55  # outboard of the rail's hook
    roof: float = 0.6  # over the rail
    lift: float = 0.5  # room above it, so the strap rides over the detent
    fit: float = 0.15  # on the groove: it has to slide
    stand_off: float = 0.1  # clear of the bracket's inner face, where the rimbase bears

    @property
    def height(self) -> float:
        return self.carriage.flare + self.lift + self.roof

    @property
    def width(self) -> float:
        truck = self.carriage
        return truck.bracket + truck.flare + self.fit + self.wall - self.stand_off

    @property
    def travel(self) -> float:
        """Slack between the detent and the step the strap comes to rest against."""
        return self.carriage.rail_end - self.carriage.detent_at - self.length


def cap_square(spec: CapSquareSpec) -> Part:
    """One strap, in its printing position: groove up, roof on the bed."""
    truck = spec.carriage
    rail = truck.rail_profile(1)
    inner, shoulder = rail[0]
    outer = rail[2][0]
    centre = inner + spec.stand_off + spec.width / 2

    with BuildPart() as strap:
        with BuildSketch(Plane.YZ.offset(-spec.length / 2)):
            near, far = inner + spec.stand_off, inner + spec.stand_off + spec.width
            Polygon(
                (near, shoulder),
                (far, shoulder),
                (far, shoulder + spec.height),
                (near, shoulder + spec.height),
                align=None,
            )
        extrude(amount=spec.length)

        with BuildSketch(Plane.YZ.offset(-spec.length / 2)):
            # The rail, carried down past the strap's underside so the groove
            # is open below, and again `lift` higher so the strap can ride over
            # the detent. Swept and then grown by the sliding clearance in one
            # go: a groove patched together from overlapping rectangles leaves
            # ledges, and a ledge inside a groove prints as an overhang.
            carried = (
                (inner, shoulder - spec.height),
                *rail,
                (outer, shoulder - spec.height),
            )
            Polygon(*carried, align=None)
            Polygon(*((y, z + spec.lift) for y, z in carried), align=None)
            offset(amount=spec.fit, kind=Kind.INTERSECTION)
        extrude(amount=spec.length, mode=Mode.SUBTRACT)

    assert strap.part is not None
    # Round the origin, then turn it over: it is fitted the other way up.
    home = strap.part.moved(Location((0, -centre, -shoulder)))
    return home.rotate(Axis.X, 180).moved(Location((0, 0, spec.height)))


def model() -> Part:
    return cap_square(CapSquareSpec())


def main() -> None:
    spec = CapSquareSpec()
    strap = cap_square(spec)
    box = strap.bounding_box().size
    print(
        f"cap square {box.X:.1f} x {box.Y:.1f} x {box.Z:.1f} mm, "
        f"{spec.travel:.1f}mm of slack past the detent"
    )
    show_object(strap, name="cap square")


if __name__ == "__main__":
    main()
