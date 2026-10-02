"""Where the guns stand, and the slides they run on.

The boat carried a 12-pounder in the bow, firing over the stem, and a 9-pounder
either side amidships, staggered and firing over the rail. At the heights the
scan gives every barrel clears its rail, and this checks that it still does in
the model rather than taking it on trust. The bow gun's rail is still notched
round the barrel where it crosses the stem, as a close look at the boat shows.

Each gun runs on a slide printed into its deck (see `cannon/slide.py`). The
slide's chocks are where the carriage stops: run out, with the muzzle over the
side, and recoiled, `travel` further inboard. Both come from the hull's lines,
so the run-out is as far as the carriage can go without touching the planking.

Millimetres of the finished model throughout, as in rig.py and awning.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from build123d import Circle, Compound, Location, Part, Plane, Pos, Rot, extrude

from cannon.assembly import assembly
from cannon.cannon import outline, trunnion_height
from cannon.carriage import CarriageSpec
from cannon.slide import slide
from hull import HullSpec, Scaled, as_part, deck_at
from lines import HullLines

# How far a carriage, run out, stands off the inside of the planking.
CLEARANCE = 0.5

# The least a barrel may clear the rail by, anywhere in its run.
MARGIN = 0.3

# How far the bow's notch round the barrel dips below the rail at the stem.
GUNPORT_DEPTH = 1.0

# How close a chock may come to the outside of the hull, which it is merged into
# where the carriage runs out right against the side.
SKIN = 1.0


@dataclass(frozen=True)
class Gun:
    """A gun as the scan places it."""

    station: float
    """along the length, as a fraction from the bow

    For the bow gun this is where its trunnions are when run out; for a
    broadside gun, where along the boat it stands, and the hull decides how far
    out it runs.
    """
    side: int
    """+1 to starboard, -1 to port, 0 on the centreline firing over the stem"""
    carriage: CarriageSpec

    def __post_init__(self) -> None:
        if self.side not in (-1, 0, 1):
            raise ValueError(f"a gun's side is -1, 0 or 1, not {self.side}")
        if not 0.0 < self.station < 1.0:
            raise ValueError(f"the gun at {self.station} is off the boat")


@dataclass(frozen=True)
class Mount:
    """A gun solved against the hull: where it runs out, and what it fires over."""

    gun: Gun
    trunnions: tuple[float, float]
    """(x, y) of the middle of the trunnion axis, run out"""
    outboard: tuple[float, float]
    """the direction it fires in, as a unit vector in plan"""
    deck: float
    """the height of the deck its carriage stands on"""
    rail: tuple[tuple[float, float], ...]
    """what it fires over, as (distance outboard of the trunnions, height) points

    For a broadside gun, the top of the bulwark from its inside face to its
    outside; for the bow gun, the sheer from the carriage's front to the stem.
    """

    @property
    def carriage(self) -> CarriageSpec:
        return self.gun.carriage

    @property
    def travel(self) -> float:
        return self.carriage.slide.travel

    @property
    def bearing(self) -> float:
        """Degrees about z that turn the carriage's muzzle end, -x, to `outboard`."""
        return math.degrees(math.atan2(-self.outboard[1], -self.outboard[0]))

    def location(self, recoil: float = 0.0) -> Location:
        """Carriage coordinates to the hull's, `recoil` millimetres inboard of run out."""
        x = self.trunnions[0] - recoil * self.outboard[0]
        y = self.trunnions[1] - recoil * self.outboard[1]
        return Pos(x, y, self.deck) * Rot(0.0, 0.0, self.bearing)

    def slide(self) -> Part:
        """The slide in the deck, its chocks just clear of the carriage at either end."""
        spec = self.carriage
        rail = slide(spec.slide, spec.fore, spec.aft + self.travel)
        return self.location() * rail

    def gunport(self, sheer: float) -> Part:
        """The notch in the bow round the barrel, as a solid to subtract.

        A cylinder on the gun's axis, run out, from the carriage's front to past
        the stem, large enough to dip `GUNPORT_DEPTH` below the rail at the stem,
        whose height there is `sheer`. It takes the rail and the stem's head down
        round the barrel.
        """
        tilt = math.radians(self.carriage.elevation)
        inner = -self.carriage.fore
        outer = self.trunnions[0] + 1.0
        radius = self.deck + self.axis_over(self.trunnions[0]) - (sheer - GUNPORT_DEPTH)
        start = Pos(self.trunnions[0] - inner, 0.0, self.deck + self.axis_over(inner)).position
        direction = (-math.cos(tilt), 0.0, math.sin(tilt))
        length = (outer - inner) / math.cos(tilt)
        return extrude(Plane(origin=start, z_dir=direction) * Circle(radius), amount=length)

    def axis_over(self, along: float, recoil: float = 0.0) -> float:
        """The axis's height above the deck, `along` millimetres outboard of run-out trunnions."""
        tilt = math.radians(self.carriage.elevation)
        return self.carriage.axis_height + (along + recoil) * math.tan(tilt)

    def axis_over_rail(self) -> float:
        """The axis above the deck where it crosses the middle of the rail, run out.

        This is the height the scan measured the broadside guns at.
        """
        return self.axis_over(0.5 * (self.rail[0][0] + self.rail[-1][0]))

    def clearance(self) -> float:
        """The least the barrel clears the rail by, anywhere from run out to recoiled.

        Recoiling only draws thicker, lower parts of the barrel over the rail if
        the muzzle is still outboard of it, so every position is checked, not
        just the ends.
        """
        spec = self.carriage
        gun = spec.gun
        tilt = math.radians(spec.elevation)
        least = math.inf
        for recoil in np.linspace(0.0, self.travel, 9):
            for along, top in self.rail:
                # How far back from the muzzle face the barrel is over this point.
                s = trunnion_height(gun) - (along + float(recoil)) / math.cos(tilt)
                if s < 0.0:
                    continue
                under = self.deck + self.axis_over(along, float(recoil))
                under -= outline(gun, s) / math.cos(tilt)
                least = min(least, under - top)
        return least


def mount(gun: Gun, spec: HullSpec, lines: HullLines) -> Mount:
    """Solve a gun against the hull, refusing one that cannot fire over its rail.

    A broadside gun runs out until its carriage is `CLEARANCE` off the inside
    of the planking, measured at the deck -- the side flares, so that is where
    it is narrowest -- or until its outer chock would come within `SKIN` of the
    outside. The bow gun's run-out is the scan's, and is only checked.
    """
    at = Scaled(spec, lines)
    carriage = gun.carriage
    slide = carriage.slide
    platform = deck_at(spec, gun.station)
    if platform is None:
        raise ValueError(f"the gun at {gun.station:.3f} stands over open bilge")
    deck = at.deck(platform)
    station = at.station(gun.station)
    inside, sheer = at.inside, at.sheer

    if gun.side == 0:
        front = station + carriage.fore
        chock = front - slide.chock
        if inside(front, deck) < carriage.half_width + CLEARANCE:
            raise ValueError(f"the bow gun's carriage does not fit the forecastle at {front:.1f}mm")
        if inside(chock, deck - slide.sink) < slide.reach + CLEARANCE:
            raise ValueError(f"the bow gun's chock does not fit the forecastle at {chock:.1f}mm")
        return Mount(
            gun=gun,
            trunnions=(station, 0.0),
            outboard=(-1.0, 0.0),
            deck=deck,
            rail=tuple(
                (station - float(x), sheer(float(x)))
                for x in np.linspace(at.station(0.0), front, 40)
            ),
        )

    # The carriage spans its own width along the boat, and the hull is not
    # quite parallel-sided over it: take the tightest.
    span = np.linspace(station - carriage.half_width, station + carriage.half_width, 5)
    inner = min(inside(float(x), deck) for x in span)
    under = min(inside(float(x), deck - slide.sink) for x in span)
    front = min(inner - CLEARANCE, under + spec.wall - SKIN - slide.chock)
    reach = front + carriage.fore
    rail_inside = min(inside(float(x), sheer(float(x))) for x in span)
    rail_outside = lines.sheer_half_width.value(station / at.factor) * at.factor
    top = max(sheer(float(x)) for x in span)
    return Mount(
        gun=gun,
        trunnions=(station, gun.side * reach),
        outboard=(0.0, float(gun.side)),
        deck=deck,
        rail=tuple((float(y) - reach, top) for y in np.linspace(rail_inside, rail_outside, 25)),
    )


def mounts(spec: HullSpec, lines: HullLines, guns: tuple[Gun, ...]) -> list[Mount]:
    """Every gun solved, each checked to clear its rail over its whole run."""
    solved = [mount(gun, spec, lines) for gun in guns]
    for m in solved:
        least = m.clearance()
        if least < MARGIN:
            raise ValueError(
                f"the gun at {m.gun.station:.3f} clears its rail by only {least:.2f}mm; "
                f"raise its carriage's axis"
            )
    return solved


def fit_guns(hull: Part, spec: HullSpec, lines: HullLines, guns: tuple[Gun, ...]) -> Part:
    """Lay each gun's slide on its deck.

    Runs after `build`, like the mast step and the awning's sockets, since the
    cavity subtraction would carve away anything added before it. Then checks,
    by probing the fitted hull, that there is deck under each corner of the
    carriage and open air over it at both ends of its run: a slide can be laid
    anywhere, but a carriage standing half over the bilge cannot run on it.
    """
    fitted = hull
    solved = mounts(spec, lines, guns)
    for m in solved:
        if m.gun.side == 0:
            head = Scaled(spec, lines).sheer(0.0)
            fitted = as_part(fitted - m.gunport(head), "cutting the bow's gunport")
    for m in solved:
        fitted = as_part(fitted + m.slide(), "laying a gun's slide")
    for m in solved:
        carriage = m.carriage
        for recoil in (0.0, m.travel):
            place = m.location(recoil)
            for x in (carriage.fore, carriage.aft):
                for y in (-carriage.half_width, carriage.half_width):
                    below = (place * Pos(x, y, -0.3)).position
                    above = (place * Pos(x, y, carriage.slide.height + 0.5)).position
                    if not fitted.is_inside(below) or fitted.is_inside(above):
                        raise RuntimeError(
                            f"the gun at {m.gun.station:.3f} has no clear deck under "
                            f"({below.X:.1f}, {below.Y:.1f})"
                        )
    return fitted


def placed(m: Mount, recoil: float = 0.0) -> Compound:
    """The gun on its carriage, standing on its slide in the hull's coordinates.

    Each piece is moved on its own: moving the compound would carry its
    location but leave its children where they were built.
    """
    place = m.location(recoil)
    pieces = []
    for piece in assembly(m.carriage).children:
        moved = place * piece
        moved.label, moved.color = piece.label, piece.color
        pieces.append(moved)
    return Compound(children=pieces)
