"""The carriage the gun sits in.

Two **brackets** -- the side pieces -- standing on a **bed**, with a **quoin**,
the wedge under the breech that sets the elevation. The trunnion pegs key into
a **trunnion hole** through each bracket. The brackets' top edge is stepped,
as on the real carriage, down toward the muzzle.

The brackets spread apart to take the gun and click shut over the trunnion
heads, so `bracket` and the pegs' `lead_in` are the two numbers that decide
whether that snap is possible: bowing a bracket out by `d` at a hole `h` above
the bed strains its surface by about `3 * bracket * d / (2 * h**2)`, and PLA
gives up somewhere around 2%.

Structural dimensions are in printed millimetres. Anything that has to match
the gun is derived from `CannonSpec`, so the carriage follows the gun's scale
without being told.

    just watch cannon/carriage.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from build123d import (
    Align,
    Box,
    BuildPart,
    BuildSketch,
    Cone,
    Location,
    Locations,
    Mode,
    Part,
    Plane,
    Polygon,
    Rectangle,
    add,
    extrude,
)
from ocp_vscode import show_object

from cannon.cannon import CannonSpec, barrel_radius, trunnion_height
from cannon.trunnion import TrunnionSpec

# Top edge of a bracket: (millimetres aft of the trunnion axis, height above
# the bed). Repeated x values are the risers of each step.
STEPS = (
    (-8.0, 1.6),
    (-4.5, 1.6),
    (-4.5, 3.4),
    (-1.8, 3.4),
    (-1.8, 7.5),
    (8.0, 7.5),
    (8.0, 5.2),
    (22.0, 5.2),
)


@dataclass(frozen=True)
class CarriageSpec:
    gun: CannonSpec = field(default_factory=CannonSpec)

    bracket: float = 0.9  # thickness of a side piece
    bed: float = 2.0
    axis_height: float = 5.6  # trunnion axis above the bed's top face
    steps: tuple[tuple[float, float], ...] = STEPS

    quoin_width: float = 2.6  # about half the gun's diameter
    # The wedge, thin end forward. It stops short of the base ring, which hangs
    # lower than the barrel it stands on.
    quoin_from: float = 10.5
    quoin_to: float = 16.5
    clearance: float = 0.1  # between the quoin's top and the breech

    @property
    def pegs(self) -> TrunnionSpec:
        return self.gun.trunnions or TrunnionSpec()

    @property
    def gap(self) -> float:
        """Between the brackets: the barrel plus what the pegs stand off it."""
        standoff = self.pegs.shank_length - self.pegs.into_barrel
        return 2 * (barrel_radius(self.gun, self.gun.trunnions_at) + standoff)

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


def _trunnion_holes(spec: CarriageSpec) -> Part:
    """Both holes, as a solid to subtract, countersunk on the inside.

    A diamond rather than a round hole: these run horizontally through an
    upright bracket, and a diamond's upper facets stand at 45 degrees, so the
    roof carries itself. The countersink is the lead-in that lets a trunnion
    head start entering before the bracket has spread the whole way.
    """
    pegs = spec.pegs
    height = spec.bed + spec.axis_height
    half = spec.gap / 2
    with BuildPart() as cutter:
        with BuildSketch(Plane.XZ):
            with Locations((0, height)):
                Rectangle(pegs.hole / math.sqrt(2), pegs.hole / math.sqrt(2), rotation=45)
        extrude(amount=half + spec.bracket + 1, both=True)
        for side in (1, -1):
            with Locations(Location((0, side * half, height), (-90 * side, 0, 0))):
                Cone(
                    pegs.hole / 2 + pegs.lead_in,
                    pegs.hole / 2,
                    pegs.lead_in,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                )

    assert cutter.part is not None
    return cutter.part


def carriage(spec: CarriageSpec) -> Part:
    half = spec.gap / 2
    fore, aft = spec.steps[0][0], spec.steps[-1][0]

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

        with BuildSketch(Plane.XZ):
            Polygon(
                (spec.quoin_from, spec.bed),
                (spec.quoin_to, spec.bed),
                (spec.quoin_to, spec.bed + spec.quoin_height),
                align=None,
            )
        extrude(amount=spec.quoin_width / 2, both=True)

        add(_trunnion_holes(spec), mode=Mode.SUBTRACT)

    assert truck.part is not None
    return truck.part


def model() -> Part:
    return carriage(CarriageSpec())


def main() -> None:
    truck = model()
    box = truck.bounding_box().size
    spec = CarriageSpec()
    strain = 3 * spec.bracket * spec.pegs.spread / (2 * spec.axis_height**2)
    print(
        f"carriage {box.X:.1f} x {box.Y:.1f} x {box.Z:.1f} mm, "
        f"brackets spread {spec.pegs.spread:.2f}mm at {strain:.1%} strain"
    )
    show_object(truck, name="carriage")


if __name__ == "__main__":
    main()
