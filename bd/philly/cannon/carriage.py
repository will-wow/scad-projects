"""The carriage the gun sits in.

Two **brackets** -- the side pieces -- standing on the deck either side of a
**bed**, with a **quoin**, the wedge under the breech that sets the elevation.
The top of each bracket is opened into a **bed** for the trunnion pin, with a
straight **slot** over it. The slot is narrower than the pin is round and only
as wide as the pin is across its flats, so the pin drops in at one angle of the
gun -- muzzle down by `TrunnionSpec.release` -- and at every other angle its
corners are under the **lips** either side, held by solid bracket.

The carriage runs on a slide in the deck (see `cannon/slide.py`). The bed is
raised over a tunnel that the slide passes through, and in the tunnel, fixed to
the brackets at their middles, are the two **clamps** that snap under the
slide's lip. Four **trucks** on the sides are the wheels a sea carriage stands
on; here they are for looks, since the slide does the running.

Nothing that holds the gun springs, and that is the whole of the point. Two
earlier schemes did. Cap squares -- little grooved blocks sliding on a hooked
rail -- were too small to print at 1:55. Sprung lips either side of the slot
held the gun for an afternoon of play and then took a set: 0.7mm of PLA bending
across its printed layers creeps a few microns each time, and the 0.12mm each
lip had to give with was soon gone. A bayonet has nothing to creep, and a child
can still take the gun out, by pushing the muzzle down to the one angle where
the flats line up and lifting.

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
    Circle,
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
# rail's top). Tallest forward, where it carries the clip, stepping down aft over
# the quoin. Repeated x values are the risers.
STEPS = (
    (-8.0, 0.0),
    (4.5, 0.0),
    (4.5, -2.6),
    (12.0, -2.6),
    (12.0, -3.6),
    (22.0, -3.6),
)


@dataclass(frozen=True)
class CarriageSpec:
    gun: CannonSpec = field(default_factory=CannonSpec)
    # The trunnion axis above the deck: the bow gun's, off the scan, which is
    # what lets it fire over the stem. The scan puts that axis 1621mm above the
    # keel and its own forecastle planking at 838; the model rounds that deck
    # to 0.48 of the hull's depth, which is 865, so the axis stands 13.9mm over
    # the deck the carriage actually sits on rather than the 14.4 the scan
    # reads over its own.
    axis_height: float = 13.9
    elevation: float = 4.1  # degrees the quoin holds the muzzle up; the bow gun's, off the scan
    slide: Slide = field(default_factory=Slide)

    bracket: float = 1.4  # thickness of a side piece
    steps: tuple[tuple[float, float], ...] = STEPS

    # The bayonet. Each bracket's top is opened into a bed with a straight slot
    # over it, and the slot is narrower than the pin is round: it passes only
    # with its flats lined up, which is one angle of the gun and no other. The
    # lips either side are solid bracket -- nothing here springs, which is the
    # point, an earlier pair of sprung lips having taken a set in an afternoon.
    cheek: float = 2.4  # how far a bracket stands over the trunnion axis
    lead: float = 0.25  # chamfer at the mouth, so the pin finds its way in
    # Where a lip's underside meets the bed, in degrees above the axis. It has
    # to be above the bed's widest point, or the 45-degree underside cuts a
    # chord off the bed and the pin can drop in but not turn.
    bite: float = 35.0

    quoin_width: float = 2.6  # about half the gun's diameter
    quoin: float = 6.0  # the wedge's length, thin end forward
    # How far the wedge stops short of the base ring, which hangs lower than the
    # barrel it would otherwise stand on.
    quoin_shy: float = 1.25
    clearance: float = 0.05  # between the quoin's top and the breech at `elevation`
    breech_clearance: float = 0.3  # between the bed and the base ring at `elevation`
    bed: float = 1.0  # least thickness of the bed, over the top of the tunnel
    headroom: float = 0.3  # between the tunnel's roof and the clamps' tops

    # For a bed that will not hold the carriage down -- it stands on two strips
    # 30mm long and 1.4mm wide -- a sacrificial pad at each corner, which snaps
    # off with a fingernail. Off by default: the print came out without them,
    # and nothing in the boat is built with them.
    tabs: float = 0.0  # diameter of each pad; 0 for none
    tab: float = 0.25  # how thick they are: a layer or two

    # Trucks, as (millimetres aft of the trunnion axis, radius). The fore pair
    # are the larger, as on a real carriage.
    trucks: tuple[tuple[float, float], ...] = ((-4.0, 3.4), (15.5, 3.0))
    truck: float = 0.8  # how far a truck stands off the side

    @property
    def pegs(self) -> TrunnionSpec:
        return self.gun.trunnions or TrunnionSpec()

    @property
    def rail_top(self) -> float:
        """The top of a bracket, and of the clip's lips, above the deck."""
        return self.axis_height + self.cheek

    @property
    def lip_underside(self) -> float:
        """Where a lip's underside leaves the slot wall, above the axis.

        It runs from there down to the bed at 45 degrees, so it carries its own
        roof, and it meets the bed `bite` degrees above the axis rather than at
        the widest point -- which is what leaves the bed a full circle for the
        pin to turn in.
        """
        radius = self.pegs.bed / 2
        bite = math.radians(self.bite)
        return radius * (math.cos(bite) + math.sin(bite)) - self.pegs.slot / 2

    @property
    def lip_clears_the_pin_by(self) -> float:
        """How far a lip's underside passes outside the turning pin."""
        radius = self.pegs.bed / 2
        bite = math.radians(self.bite)
        return radius * (math.cos(bite) + math.sin(bite)) / math.sqrt(2) - self.pegs.shank / 2

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


def _slots(spec: CarriageSpec) -> Part:
    """Both bayonet slots, as a solid to subtract: a bed with a way in over it.

    The bed is round and takes the pin's full diameter with room to turn; the
    way in over it is narrower than that, and only as wide as the pin is across
    its flats. So the pin goes down it at one angle of the gun and is held by
    solid metal at every other -- there is no spring here, and nothing to take
    a set. The two sprung lips this replaced held the gun for an afternoon of
    play and then went soft: 0.7mm of PLA bending across its layers creeps a few
    microns each time.

    The lips' undersides run down at 45 degrees and meet the bed `bite` degrees
    above the axis, not at its widest point. Run them to the widest point and
    they pass 1.03mm from the axis, inside the 1.3mm the pin needs, and the pin
    drops in and then jams instead of turning.

    Returns a part to subtract rather than cutting the caller's, because a
    builder only nests into its parent when both are opened in the same Python
    frame: a BuildSketch opened down here would quietly go nowhere.
    """
    axis, top = spec.axis_height, spec.rail_top
    radius = spec.pegs.bed / 2
    half = spec.pegs.slot / 2
    bite = math.radians(spec.bite)
    meets = (radius * math.cos(bite), radius * math.sin(bite))
    lead = spec.lead
    over = 1.0  # how far the cut stands above the bracket, so the mouth is open

    with BuildPart() as cutter:
        for side in (1, -1):
            plane = Plane.XZ.offset(-side * (spec.gap / 2 - 0.1))
            with BuildSketch(plane):
                with BuildLine():
                    Polyline(
                        (-(half + lead), top + over),
                        (-(half + lead), top),
                        (-half, top - lead),
                        (-half, axis + spec.lip_underside),
                        (-meets[0], axis + meets[1]),
                    )
                    CenterArc(
                        (0, axis), radius, start_angle=180 - spec.bite, arc_size=180 + 2 * spec.bite
                    )
                    Polyline(
                        (meets[0], axis + meets[1]),
                        (half, axis + spec.lip_underside),
                        (half, top - lead),
                        (half + lead, top),
                        (half + lead, top + over),
                        (-(half + lead), top + over),
                    )
                make_face()
            extrude(amount=-side * (spec.bracket + 0.2))

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
    if spec.pegs.slot >= spec.pegs.shank:
        raise ValueError("the way in is wider than the pin is round; it would lift out")
    if spec.lip_clears_the_pin_by <= 0.05:
        raise ValueError("the lips' undersides cut into the bed; the pin could not turn")

    # Built before the builder opens: inside it, a bare Polygon is taken as a
    # sketch operation on the part and refused.
    tunnel, clamps, slots = _tunnel(spec), _clamps(spec), _slots(spec)
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

        with BuildSketch(Plane.XZ):
            Polygon(
                (spec.quoin_from, spec.bed_top),
                (spec.quoin_to, spec.bed_top),
                (spec.quoin_to, spec.quoin_top),
                align=None,
            )
        extrude(amount=spec.quoin_width / 2, both=True)

        add(slots, mode=Mode.SUBTRACT)

        if spec.tabs:
            with BuildSketch(Plane.XY):
                with Locations(
                    *((x, side * (half + spec.bracket)) for x in (fore, aft) for side in (1, -1))
                ):
                    Circle(spec.tabs / 2)
            extrude(amount=spec.tab)

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
        f"trunnion axis {spec.axis_height:.2f}mm above the deck; "
        f"the pin lifts out at {spec.pegs.release:.0f} degrees and is held by "
        f"{spec.pegs.locked_by(spec.elevation - spec.pegs.release):.2f}mm where it rests, "
        f"clamps strained {spec.slide.strain(spec.arm):.2%} clipping on"
    )
    show_object(truck, name="carriage")


if __name__ == "__main__":
    main()
