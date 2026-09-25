"""The carriage the gun sits in.

Two **brackets** -- the side pieces -- standing on a **bed**, with a **quoin**,
the wedge under the breech that sets the elevation. Each bracket's top edge
carries a **rail**, flared out either side, with a semicircular **trunnion bed**
notched into it. The gun drops into the two beds and a **cap square** slides
aft along each rail to close over its trunnion, as the ironwork does on the
real gun.

Nothing here is a spring. A clip small enough to fit a bracket at this scale
would have to flex about 0.4mm on a 3mm arm, which is three times the strain
PLA takes -- so the gun is held by a part that slides rather than one that
bends, and a hard knock slides the cap square or lifts the gun out instead of
breaking anything.

Structural dimensions are in printed millimetres. Anything that has to match
the gun is derived from `CannonSpec`, so the carriage follows the gun's scale
without being told.

    just watch cannon/carriage.py
"""

from __future__ import annotations

from dataclasses import dataclass, field

from build123d import (
    Align,
    Box,
    BuildLine,
    BuildPart,
    BuildSketch,
    CenterArc,
    Locations,
    Mode,
    Part,
    Plane,
    Polygon,
    Polyline,
    add,
    extrude,
    make_face,
)
from ocp_vscode import show_object

from cannon.cannon import CannonSpec, barrel_radius, trunnion_height
from cannon.trunnion import TrunnionSpec

# Top edge of a bracket: (millimetres aft of the trunnion axis, height above
# the bed). Tallest forward, where it carries the trunnion and its cap square,
# stepping down aft over the quoin. Repeated x values are the risers.
STEPS = (
    (-8.0, 5.65),
    (4.5, 5.65),
    (4.5, 3.6),
    (12.0, 3.6),
    (12.0, 2.6),
    (22.0, 2.6),
)


@dataclass(frozen=True)
class CarriageSpec:
    gun: CannonSpec = field(default_factory=CannonSpec)

    bracket: float = 1.4  # thickness of a side piece; nothing here has to flex
    bed: float = 2.0
    steps: tuple[tuple[float, float], ...] = STEPS

    flare: float = 0.5  # the rail's outward hook, and the chamfer facing it
    rail_end: float = 4.5  # aft end of the rail, where the bracket steps down
    detent: float = 0.25  # bump the cap square clicks over on its way aft
    detent_at: float = -1.9  # where that bump sits, aft of the trunnion axis

    quoin_width: float = 2.6  # about half the gun's diameter
    # The wedge, thin end forward. It stops short of the base ring, which hangs
    # lower than the barrel it stands on.
    quoin_from: float = 10.5
    quoin_to: float = 16.5
    clearance: float = 0.1  # between the quoin's top and the breech

    @property
    def pegs(self) -> TrunnionSpec:
        return self.gun.trunnions or TrunnionSpec()

    def rail_profile(self, side: int) -> tuple[tuple[float, float], ...]:
        """The rail's top, in (y, z): what a cap square grips.

        Hooked outboard, chamfered inboard. A cap square's outer leg catches
        under the hook and its inner lip rides the chamfer, so lifting it would
        have to drive it further under the hook. Both faces sit at 45 degrees,
        and only the hook is an undercut, which prints as its own roof.
        """
        rail_top = self.bed + self.top
        inner, outer = side * self.gap / 2, side * (self.gap / 2 + self.bracket)
        return (
            (inner, rail_top - self.flare),
            (inner + side * self.flare, rail_top),
            (outer + side * self.flare, rail_top),
            (outer, rail_top - self.flare),
        )

    @property
    def axis_height(self) -> float:
        """Trunnion axis above the bed: the bed is notched into the rail's top."""
        return self.top - self.pegs.bed / 2

    @property
    def top(self) -> float:
        """The rail's top, above the bed's top face."""
        return max(height for _, height in self.steps)

    @property
    def gap(self) -> float:
        """Between the brackets: the barrel plus what the pegs stand off it."""
        return 2 * (barrel_radius(self.gun, self.gun.trunnions_at) + self.pegs.stand_off)

    @property
    def length(self) -> float:
        return self.steps[-1][0] - self.steps[0][0]

    def gun_radius(self, x: float) -> float:
        """Radius of the bare barrel `x` millimetres aft of the trunnion axis."""
        gun = self.gun
        along = (trunnion_height(gun) + x) / (gun.length * gun.scale)
        return barrel_radius(gun, min(along, 1.0))

    @property
    def quoin_height(self) -> float:
        return self.axis_height - self.gun_radius(self.quoin_to) - self.clearance


def _beds(spec: CarriageSpec) -> Part:
    """Both trunnion beds, as a solid to subtract.

    A semicircle notched down from the rail's top with the way in left open
    above it, so the gun drops straight in and nothing has to bridge a roof.
    """
    radius = spec.pegs.bed / 2
    height = spec.bed + spec.axis_height
    reach = 4 * radius
    with BuildPart() as cutter:
        with BuildSketch(Plane.XZ):
            with BuildLine():
                CenterArc((0, height), radius, start_angle=180, arc_size=180)
                Polyline(
                    (radius, height),
                    (radius, height + reach),
                    (-radius, height + reach),
                    (-radius, height),
                )
            make_face()
        extrude(amount=spec.gap / 2 + spec.bracket + spec.flare, both=True)

    assert cutter.part is not None
    return cutter.part


def carriage(spec: CarriageSpec) -> Part:
    half = spec.gap / 2
    fore, aft = spec.steps[0][0], spec.steps[-1][0]
    rail_top = spec.bed + spec.top

    with BuildPart() as truck:
        with Locations(((fore + aft) / 2, 0, 0)):
            Box(
                spec.length,
                spec.gap + 2 * spec.bracket,
                spec.bed,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )

        outline = (
            (fore, spec.bed),
            *((x, spec.bed + h) for x, h in spec.steps),
            (aft, spec.bed),
        )
        for side in (1, -1):
            with BuildSketch(Plane.XZ.offset(-side * half)):
                Polygon(*outline, align=None)
            extrude(amount=-side * spec.bracket)

            # The rail the cap square grips: hooked outboard, chamfered
            # inboard. Built by cutting the bracket's top corners back to the
            # profile and adding the hook outside it.
            inner, outer = side * half, side * (half + spec.bracket)
            with BuildSketch(Plane.YZ.offset(fore)):
                Polygon(
                    (inner, rail_top),
                    (inner + side * spec.flare, rail_top),
                    (inner, rail_top - spec.flare),
                    align=None,
                )
            extrude(amount=spec.rail_end - fore, mode=Mode.SUBTRACT)

            with BuildSketch(Plane.YZ.offset(fore)):
                Polygon(
                    (outer, rail_top),
                    (outer + side * spec.flare, rail_top),
                    (outer, rail_top - spec.flare),
                    align=None,
                )
            extrude(amount=spec.rail_end - fore)

            # The bump the cap square clicks over, a ridge across the rail with
            # both its flanks at the overhang limit.
            crown = side * (half + spec.flare + spec.bracket / 2)
            with BuildSketch(Plane.XZ.offset(-crown)):
                Polygon(
                    (spec.detent_at - spec.detent, rail_top),
                    (spec.detent_at + spec.detent, rail_top),
                    (spec.detent_at, rail_top + spec.detent),
                    align=None,
                )
            extrude(amount=spec.bracket / 2, both=True)

        with BuildSketch(Plane.XZ):
            Polygon(
                (spec.quoin_from, spec.bed),
                (spec.quoin_to, spec.bed),
                (spec.quoin_to, spec.bed + spec.quoin_height),
                align=None,
            )
        extrude(amount=spec.quoin_width / 2, both=True)

        add(_beds(spec), mode=Mode.SUBTRACT)

    assert truck.part is not None
    return truck.part


def model() -> Part:
    return carriage(CarriageSpec())


def main() -> None:
    spec = CarriageSpec()
    truck = carriage(spec)
    box = truck.bounding_box().size
    print(
        f"carriage {box.X:.1f} x {box.Y:.1f} x {box.Z:.1f} mm, "
        f"trunnion axis {spec.axis_height:.2f}mm above the bed"
    )
    show_object(truck, name="carriage")


if __name__ == "__main__":
    main()
