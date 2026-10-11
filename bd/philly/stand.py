"""A stand for the hull to sit on: an X in section, with a cradle cut into its top.

    just watch stand.py

The section is a bar along the bottom and another along the top, joined by an X
whose arms meet in a solid neck, so the two triangles left either side are open
right through. It prints standing on one end, the X flat on the bed: every wall
then rises straight up and nothing overhangs but the lettering, which stands
0.6mm proud.

The cradle -- the word is Falconer's, for the frame a hull rests in ashore -- is
the hull's own bottom, set out by a clearance so the boat lifts in and out.
`Scaled.inside` already offsets the flared and bowed side perpendicular to
itself for the planking; asked for a negative thickness, the same line lies
outside the hull instead, so the cradle is a loft through those sections
rather than an offset of the hull's solid. The bottom is flat here, so the
hull rests on the cradle's floor and the clearance is all at the sides. The
hull narrows both ways from its greatest breadth, so it cannot slide out fore
and aft either, though it narrows slowly enough that it can shuffle the best
part of a centimetre before its sides bear.

The name is lettered on the top face of the base, each side reading upright
from its own side. Libre Caslon, since Caslon is what the Declaration was
first printed in that summer.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import numpy as np
from build123d import (
    Align,
    Face,
    Kind,
    Part,
    Plane,
    Polyline,
    Pos,
    Rot,
    Text,
    Vector,
    extrude,
    loft,
    make_face,
    offset,
)
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from ocp_vscode import show_object

from hull import SIDE_SAMPLES, HullSpec, Scaled, as_part
from lines import HullLines

FONT = Path(__file__).parent / "designs" / "fonts" / "LibreCaslonText[wght].ttf"

# Sections in the cradle's loft. The lines bend gently this far from either end.
CRADLE_STATIONS = 13

# How far the lettering is sunk into the face it stands on, so the union fuses
# rather than touching.
SINK = 0.2


@dataclass(frozen=True)
class Line:
    """One line of lettering."""

    text: str
    size: float
    """the font size, in millimetres; Caslon's capitals are 0.76 of it"""


@dataclass(frozen=True)
class Lettering:
    """The name on the base, the first line innermost."""

    lines: tuple[Line, ...] = (Line("PHILADELPHIA", 8.0), Line("1776 US GUNDELO", 6.0))
    weight: float = 700.0
    """on the font's own axis, 400 to 700"""
    grow: float = 0.15
    """how far every letter is fattened all round

    Caslon's hairlines are about 0.3mm at these sizes, under a nozzle's width.
    This takes the thinnest stroke past 0.4mm and leaves every counter open.
    """
    tracking: float = 0.5
    """added between letters

    Capitals set for an inscription are spaced wider than in a line of text, and
    without it the fattened letters of the tighter pairs touch -- which prints
    as one blot and leaves OCCT a union it cannot make.
    """
    proud: float = 0.6
    margin: float = 2.0
    """from the outer edge of the base to the outermost line"""
    leading: float = 2.0
    """between lines"""


@dataclass(frozen=True)
class Stand:
    """What to build, in millimetres of the finished print."""

    station: float = 0.4
    """the middle of the stand, as a fraction of the hull's length from the bow"""
    length: float = 120.0
    breadth: float = 80.0
    height: float = 20.0
    base: float = 2.0
    """the bottom bar's thickness at the sides"""
    top: float = 6.0
    """the top bar's thickness at the sides"""
    neck: float = 24.0
    """the breadth of the solid where the X's arms cross"""
    cradle: float = 4.0
    """how deep the hull sits"""
    clearance: float = 0.6
    """between the hull's sides and the cradle's, square to the side"""
    lettering: Lettering | None = field(default_factory=Lettering)

    @property
    def slope(self) -> float:
        """The rise of each arm of the X per millimetre across."""
        return (self.height - self.top - self.base) / self.breadth

    @property
    def crossing(self) -> float:
        """The height at which the arms of the X cross."""
        return (self.base + self.height - self.top) / 2.0

    @property
    def floor(self) -> float:
        """The cradle's floor, above the bottom of the stand."""
        return self.height - self.cradle


def _extruded(points: list[tuple[float, float]], x0: float, length: float) -> Part:
    """A section given as (y, z) points, run fore and aft from `x0`."""
    face = make_face(Polyline(*[(x0, y, z) for y, z in points], close=True))
    return extrude(face, amount=length, dir=(1.0, 0.0, 0.0))


def _body(stand: Stand, x0: float) -> Part:
    """The X, its bottom at z = 0: a block with the two triangles either side cut away.

    Each triangle is the space between the arms, stopped short of the crossing by
    the neck.
    """
    half = stand.breadth / 2.0
    block = _extruded(
        [(-half, 0.0), (half, 0.0), (half, stand.height), (-half, stand.height)], x0, stand.length
    )
    inner = stand.neck / 2.0
    spread = stand.slope * inner
    for side in (-1.0, 1.0):
        gap = [
            (side * half, stand.base),
            (side * inner, stand.crossing - spread),
            (side * inner, stand.crossing + spread),
            (side * half, stand.height - stand.top),
        ]
        block = as_part(block - _extruded(gap, x0, stand.length), "opening the X")
    return block


def _cradle(stand: Stand, at: Scaled, x0: float, top: float) -> Part:
    """The hull's bottom and sides set out by the clearance, from the bottom up past `top`.

    Every section has the same number of points, which keeps the loft cheap; see
    `hull._side_profile`.
    """
    sections = []
    for x in np.linspace(x0 - 1.0, x0 + stand.length + 1.0, CRADLE_STATIONS):
        bottom = at.bottom(float(x))
        side = [
            (at.inside(float(x), float(z), -stand.clearance), float(z))
            for z in np.linspace(bottom, top + 1.0, SIDE_SAMPLES)
        ]
        points = [(x, -y, z) for y, z in reversed(side)] + [(x, y, z) for y, z in side]
        sections.append(make_face(Polyline(*points, close=True)))
    return loft(sections)


@cache
def _font(weight: float) -> Path:
    """A static instance of the variable font, which is what OCCT can read."""
    path = Path(tempfile.gettempdir()) / f"LibreCaslonText-{weight:.0f}.ttf"
    instantiateVariableFont(TTFont(FONT), {"wght": weight}).save(path)
    return path


def glyphs(line: Line, lettering: Lettering) -> list[Face]:
    """The line's letters as faces on the XY plane, spaced, centred on the origin and fattened.

    A variable font draws a letter as overlapping outlines, which are fused into
    one face per letter before it is grown.
    """
    text = Text(
        line.text,
        line.size,
        font_path=str(_font(lettering.weight)),
        align=(Align.CENTER, Align.CENTER),
    )
    faces = text.faces()
    letters = sorted(
        faces[0].fuse(*faces[1:]).clean().faces(), key=lambda face: face.bounding_box().min.X
    )
    middle = (len(letters) - 1) / 2.0
    return [
        Pos((i - middle) * lettering.tracking, 0.0, 0.0)
        * offset(face, lettering.grow, kind=Kind.ARC).faces()[0]
        for i, face in enumerate(letters)
    ]


def _lettering(stand: Stand, lettering: Lettering, middle: float, z0: float) -> list[Part]:
    """Both sides' lettering, standing on the top face of the base.

    The lines run fore and aft and the letters' tops point up the slope, toward
    the neck, so each side reads from its own side: forward is to the reader's
    left to starboard and to their right to port.
    """
    half = stand.breadth / 2.0
    run = half - stand.neck / 2.0
    rise = stand.slope * run
    across = float(np.hypot(run, rise))

    letters: list[Part] = []
    for side in (1.0, -1.0):
        edge = Vector(middle, side * half, z0 + stand.base)
        up_slope = Vector(0.0, -side * run, rise) / across
        normal = Vector(0.0, side * rise, run) / across
        reading = Vector(-side, 0.0, 0.0)

        out = lettering.margin
        for line in reversed(lettering.lines):
            faces = glyphs(line, lettering)
            height = max(f.bounding_box().max.Y for f in faces) - min(
                f.bounding_box().min.Y for f in faces
            )
            plane = Plane(
                origin=edge + up_slope * (out + height / 2.0) - normal * SINK,
                x_dir=reading,
                z_dir=normal,
            )
            for face in faces:
                letters.append(
                    extrude(plane.location * face, amount=lettering.proud + SINK, dir=normal)
                )
            out += height + lettering.leading
    return letters


def placed(spec: HullSpec, lines: HullLines, stand: Stand) -> Part:
    """The stand under the hull, in the hull's own coordinates."""
    at = Scaled(spec, lines)
    middle = at.station(stand.station)
    x0 = middle - stand.length / 2.0
    z0 = at.bottom(middle) - stand.floor

    body = Pos(0.0, 0.0, z0) * _body(stand, x0)
    body = as_part(body - _cradle(stand, at, x0, z0 + stand.height), "cutting the cradle")
    if stand.lettering is not None:
        letters = _lettering(stand, stand.lettering, middle, z0)
        body = as_part(body + letters, "lettering the base")
    return body


def printed(spec: HullSpec, lines: HullLines, stand: Stand) -> Part:
    """The stand on one end, the X flat on the bed."""
    upright = Rot(0.0, -90.0, 0.0) * placed(spec, lines, stand)
    box = upright.bounding_box()
    return as_part(Pos(-box.center().X, -box.center().Y, -box.min.Z) * upright, "standing on end")


if __name__ == "__main__":
    import lines as hull_lines
    from main import HULL, STAND

    part = printed(HULL, hull_lines.load(), STAND)
    size = part.bounding_box().size
    print(f"stand {size.X:.1f} x {size.Y:.1f} x {size.Z:.1f} mm, {part.volume / 1000:.1f} cm^3")
    show_object(part, name="stand")
