"""The carriage the gun sits in.

Two **brackets** -- the side pieces -- standing on the deck either side of a
**bed**, with a **quoin**, the wedge under the breech that sets the elevation.
Each bracket's top edge carries a **rail**, flared out either side, with a
semicircular **trunnion bed** notched into it. The gun drops into the two beds
and a **cap square** slides aft along each rail to close over its trunnion,
until it comes up against the **hinge** block the real strap is pinned to.

The carriage runs on a slide in the deck (see `cannon/slide.py`). The bed is
raised over a tunnel that the slide passes through, and in the tunnel, fixed to
the brackets at their middles, are the two **clamps** that snap under the
slide's lip. Four **trucks** on the sides are the wheels a sea carriage stands
on; here they are for looks, since the slide does the running.

Nothing that holds the gun is a spring. A clip small enough to fit a bracket at
this scale would have to flex about 0.4mm on a 3mm arm, which is three times the
strain PLA takes -- so the gun is held by a part that slides rather than one
that bends. The clamps do bend, but they are 13mm long and bend in the plane of
the bed, which keeps them well inside that limit.

The carriage is built to put the trunnion axis at `axis_height` above the deck,
which is what the gun needs to fire over the rail; the bed and brackets are
derived from it, and anything that has to match the gun comes from
`CannonSpec`. Structural dimensions are in printed millimetres.

    just watch cannon/carriage.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from build123d import (
    Align,
    Box,
    BuildLine,
    BuildPart,
    BuildSketch,
    CenterArc,
    Cone,
    Locations,
    Mode,
    Part,
    Plane,
    Polygon,
    Polyline,
    Pos,
    Rot,
    add,
    extrude,
    make_face,
)
from ocp_vscode import show_object

from cannon.cannon import CannonSpec, barrel_radius, base_ring_radius, trunnion_height
from cannon.slide import Slide
from cannon.trunnion import TrunnionSpec

# Top edge of a bracket: (millimetres aft of the trunnion axis, height below the
# rail's top). Tallest forward, where it carries the trunnion and its cap square,
# stepping down aft over the quoin. Repeated x values are the risers.
STEPS = (
    (-8.0, 0.0),
    (4.5, 0.0),
    (4.5, -2.05),
    (12.0, -2.05),
    (12.0, -3.05),
    (22.0, -3.05),
)


@dataclass(frozen=True)
class CarriageSpec:
    gun: CannonSpec = field(default_factory=CannonSpec)
    # The trunnion axis above the deck. The default is the bow gun's, 14.1mm
    # above the forecastle off the scan: high enough to fire over the stem.
    axis_height: float = 14.1
    elevation: float = 4.1  # degrees the quoin holds the muzzle up; the bow gun's, off the scan
    slide: Slide = field(default_factory=Slide)

    bracket: float = 1.4  # thickness of a side piece
    steps: tuple[tuple[float, float], ...] = STEPS

    flare: float = 0.5  # the rail's outward hook, and the chamfer facing it
    rail_end: float = 4.5  # aft end of the rail, where the bracket steps down
    detent: float = 0.25  # bump the cap square clicks over on its way aft
    detent_at: float = -1.9  # where that bump sits, aft of the trunnion axis
    hinge: float = 1.2  # length of the block that stops the cap square going aft
    hinge_height: float = 1.1  # its top above the rail: as tall as a seated cap square

    quoin_width: float = 2.6  # about half the gun's diameter
    quoin: float = 6.0  # the wedge's length, thin end forward
    # How far the wedge stops short of the base ring, which hangs lower than the
    # barrel it would otherwise stand on.
    quoin_shy: float = 1.25
    clearance: float = 0.05  # between the quoin's top and the breech at `elevation`
    breech_clearance: float = 0.3  # between the bed and the base ring at `elevation`
    bed: float = 1.0  # least thickness of the bed, over the top of the tunnel
    headroom: float = 0.3  # between the tunnel's roof and the clamps' tops

    # Trucks, as (millimetres aft of the trunnion axis, radius). The fore pair
    # are the larger, as on a real carriage.
    trucks: tuple[tuple[float, float], ...] = ((-4.0, 3.4), (15.5, 3.0))
    truck: float = 0.8  # how far a truck stands off the side

    @property
    def pegs(self) -> TrunnionSpec:
        return self.gun.trunnions or TrunnionSpec()

    @property
    def rail_top(self) -> float:
        """The rail's top above the deck: the trunnion bed is notched down into it."""
        return self.axis_height + self.pegs.bed / 2

    def rail_profile(self, side: int) -> tuple[tuple[float, float], ...]:
        """The rail's top, in (y, z): what a cap square grips.

        Hooked outboard, chamfered inboard. A cap square's outer leg catches
        under the hook and its inner lip rides the chamfer, so lifting it would
        have to drive it further under the hook. Both faces sit at 45 degrees,
        and only the hook is an undercut, which prints as its own roof.
        """
        inner, outer = side * self.gap / 2, side * (self.gap / 2 + self.bracket)
        return (
            (inner, self.rail_top - self.flare),
            (inner + side * self.flare, self.rail_top),
            (outer + side * self.flare, self.rail_top),
            (outer, self.rail_top - self.flare),
        )

    @property
    def gap(self) -> float:
        """Between the brackets: the barrel plus what the pegs stand off it."""
        return 2 * (barrel_radius(self.gun, self.gun.trunnions_at) + self.pegs.stand_off)

    @property
    def half_width(self) -> float:
        """Centreline to the outside of the trucks: what has to clear the hull."""
        return self.gap / 2 + self.bracket + (self.truck if self.trucks else 0.0)

    @property
    def fore(self) -> float:
        return self.steps[0][0]

    @property
    def aft(self) -> float:
        return self.steps[-1][0]

    @property
    def length(self) -> float:
        return self.aft - self.fore

    def gun_radius(self, x: float) -> float:
        """Radius of the bare barrel `x` millimetres aft of the trunnion axis."""
        gun = self.gun
        along = (trunnion_height(gun) + x) / (gun.length * gun.scale)
        return barrel_radius(gun, min(along, 1.0))

    @property
    def breech_drop(self) -> float:
        """How far below the axis the breech reaches with the muzzle at `elevation`.

        The base ring is the widest thing aft and the cascabel's button the
        furthest; whichever the tilt carries lower.
        """
        gun = self.gun
        tilt = math.radians(self.elevation)
        cal = gun.calibre * gun.scale
        ring = gun.length * gun.scale - trunnion_height(gun)
        button = ring + (gun.base_of_breech + gun.cascabel_neck + gun.button / 2) * cal
        return max(
            ring * math.sin(tilt) + base_ring_radius(gun) * math.cos(tilt),
            button * math.sin(tilt) + gun.button / 2 * cal * math.cos(tilt),
        )

    @property
    def bed_top(self) -> float:
        """The bed's upper face above the deck: clear of the breech at `elevation`."""
        return self.axis_height - self.breech_drop - self.breech_clearance

    @property
    def quoin_to(self) -> float:
        """The quoin's aft end, a little forward of where the base ring begins."""
        gun = self.gun
        ring = gun.base_ring * gun.calibre * gun.scale
        start = gun.length * gun.scale - ring - ring / math.sin(math.radians(gun.max_overhang))
        return start - trunnion_height(gun) - self.quoin_shy

    @property
    def quoin_from(self) -> float:
        return self.quoin_to - self.quoin

    @property
    def quoin_top(self) -> float:
        """The quoin's aft edge above the deck, where the breech comes to rest.

        With the muzzle up by `elevation` the barrel's underside there sits
        x.tan(elevation) lower than the axis drops, and its radius is spread
        over 1/cos(elevation) of height.
        """
        tilt = math.radians(self.elevation)
        return (
            self.axis_height
            - self.quoin_to * math.tan(tilt)
            - self.gun_radius(self.quoin_to) / math.cos(tilt)
            - self.clearance
        )

    @property
    def roof(self) -> float:
        """The tunnel's roof where it meets a bracket; it rises 45 degrees to the middle.

        Low enough that the bed over it keeps its thickness, high enough to
        clear the clamps' tops -- which, standing inboard of the brackets, are
        under a higher part of the roof than its foot.
        """
        return self.slide.height + self.headroom - (self.gap / 2 - self.slide.reach)

    @property
    def arm(self) -> float:
        """Length of one clamp's free arm, from the root block to its jaw's end."""
        return (self.length - self.slide.root) / 2


def _beds(spec: CarriageSpec) -> Part:
    """Both trunnion beds, as a solid to subtract.

    A semicircle notched down from the rail's top with the way in left open
    above it, so the gun drops straight in and nothing has to bridge a roof.

    Returns a part to subtract rather than cutting the caller's, because a
    builder only nests into its parent when both are opened in the same Python
    frame: a BuildSketch opened down here would quietly go nowhere.
    """
    radius = spec.pegs.bed / 2
    height = spec.axis_height
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


def _tunnel(spec: CarriageSpec) -> Part:
    """The passage under the bed that the slide runs through, as a solid to subtract.

    Its roof is a gable at 45 degrees, not a flat span, so it prints without
    bridging.
    """
    half = spec.gap / 2
    section = Polygon(
        (-half, -1.0),
        (half, -1.0),
        (half, spec.roof),
        (0.0, spec.roof + half),
        (-half, spec.roof),
        align=None,
    )
    return Pos(spec.fore - 1.0, 0, 0) * extrude(Plane.YZ * section, spec.length + 2.0)


def _clamps(spec: CarriageSpec) -> Part:
    """Both clamps, each fixed to its bracket at its middle with a jaw at each end.

    A clamp runs the whole length of the carriage, so the jaws are what meet the
    chocks at either end of the carriage's run.
    """
    slide = spec.slide
    middle = (spec.fore + spec.aft) / 2
    inner = slide.head / 2 + slide.fit
    parts = []
    for side in (1, -1):
        arm = Pos(middle, side * (inner + slide.reach) / 2, slide.height / 2) * Box(
            spec.length, slide.reach - inner, slide.height
        )
        root = Pos(middle, side * (slide.reach + spec.gap / 2) / 2, slide.height / 2) * Box(
            slide.root, spec.gap / 2 - slide.reach + 0.01, slide.height
        )
        jaw = extrude(Plane.YZ * Polygon(*slide.jaw_profile(side), align=None), slide.jaw)
        parts += [
            arm,
            root,
            Pos(spec.fore, 0, 0) * jaw,
            Pos(spec.aft - slide.jaw, 0, 0) * jaw,
        ]
    clamps = parts[0]
    for extra in parts[1:]:
        clamps += extra
    return clamps


def _trucks(spec: CarriageSpec) -> Part:
    """The wheels, as cones cut off at their outer faces.

    Coned at 45 degrees rather than squared, so each prints standing off the
    side with nothing under it steeper than that, and touching the deck at the
    bottom of its rim.
    """
    wall = spec.gap / 2 + spec.bracket
    parts = []
    for x, radius in spec.trucks:
        for side in (1, -1):
            wheel = Cone(
                radius,
                radius - spec.truck,
                spec.truck,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
            turned = Rot(-side * 90, 0, 0) * wheel
            parts.append(Pos(x, side * wall, radius) * turned)
    trucks = parts[0]
    for extra in parts[1:]:
        trucks += extra
    return trucks


def carriage(spec: CarriageSpec) -> Part:
    half = spec.gap / 2
    fore, aft = spec.fore, spec.aft
    rail_top = spec.rail_top
    slide = spec.slide

    if spec.bed_top - (spec.roof + half) < spec.bed:
        raise ValueError(
            f"the bed would be {spec.bed_top - spec.roof - half:.2f}mm over the tunnel; "
            f"raise the axis or lower the slide"
        )
    if half - slide.reach < slide.snap + 0.1:
        raise ValueError("the clamps have no room to spread over the slide's head")
    if rail_top + min(h for _, h in spec.steps) <= spec.bed_top:
        raise ValueError("the brackets' after steps are below the bed")

    # Built before the builder opens: inside it, a bare Polygon is taken as a
    # sketch operation on the part and refused.
    tunnel, clamps, beds = _tunnel(spec), _clamps(spec), _beds(spec)
    trucks = _trucks(spec) if spec.trucks else None

    with BuildPart() as truck:
        with Locations(((fore + aft) / 2, 0, 0)):
            Box(
                spec.length,
                spec.gap + 2 * spec.bracket,
                spec.bed_top,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
        add(tunnel, mode=Mode.SUBTRACT)
        add(clamps)
        if trucks is not None:
            add(trucks)

        outline = (
            (fore, spec.bed_top),
            *((x, rail_top + h) for x, h in spec.steps),
            (aft, spec.bed_top),
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

            # What the cap square comes to rest against. Without it the strap
            # slides on aft past the rail's end and off, and the gun with it.
            low = rail_top + spec.steps[2][1]
            high = rail_top + spec.hinge_height
            with Locations(
                (spec.rail_end + spec.hinge / 2, side * (half + spec.bracket / 2), (low + high) / 2)
            ):
                Box(spec.hinge, spec.bracket, high - low)

        with BuildSketch(Plane.XZ):
            Polygon(
                (spec.quoin_from, spec.bed_top),
                (spec.quoin_to, spec.bed_top),
                (spec.quoin_to, spec.quoin_top),
                align=None,
            )
        extrude(amount=spec.quoin_width / 2, both=True)

        add(beds, mode=Mode.SUBTRACT)

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
        f"trunnion axis {spec.axis_height:.2f}mm above the deck, "
        f"clamps strained {spec.slide.strain(spec.arm):.2%} clipping on"
    )
    show_object(truck, name="carriage")


if __name__ == "__main__":
    main()
