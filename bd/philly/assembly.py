"""The whole boat, assembled, for looking at rather than printing.

    just watch

The parts are exported separately and each lies the way it wants to print, so
nothing in dist/ shows what the boat actually looks like. This stands the mast
in its socket and hangs the sails on the yards, which is the only way to judge
whether the rig's proportions are right.

The sails are the one lie. Real canvas bellies out; these are flat plates
standing exactly between their yards. They are in the right place and the right
size, which is what the proportions depend on.

Nothing here is meant to be printed -- the parts overlap where they fit
together, so it is one picture, not a manifold solid. `just build` is still the
thing that writes files.
"""

from __future__ import annotations

from build123d import Compound, Part, Pos, Rot
from ocp_vscode import show_object

import lines as hull_lines
import rig as rigging
from hull import build
from main import HULL, RIG


def _stepped_mast(lines, seat) -> Part:
    """The mast standing on the bottom of its bore, where it comes to rest."""
    return Pos(seat.station, 0.0, seat.floor) * rigging.upright_mast(HULL, lines, RIG)


def _hung_sails(lines, seat) -> list[Part]:
    """Each sail turned upright and slid onto the pair of yards it belongs to.

    A sail is built lying down: its height runs along x, its width along y, and
    its thickness along z. Rotating -90 degrees about y carries x up to z and z
    round to -x, so the height stands up, the width stays athwartships, and the
    plate ends up facing fore and aft -- which is how a square sail hangs.

    The corner eyes sit a neck's length forward of the plate, so the whole sail
    shifts aft by that much to put the eyes on the yards. That gap is real, and
    load-bearing: it is what keeps the plate from fouling the mast.
    """
    radius = rigging.yard_radius(HULL, lines, RIG)
    offset = rigging.stand_off(HULL, lines, RIG)

    hung = []
    for (width, height), pair in zip(
        rigging.sail_sizes(RIG), (RIG.course, RIG.topsail), strict=True
    ):
        middle = seat.floor + 0.5 * (pair[0] + pair[1]) * RIG.mast_length
        flat = rigging.sail(RIG, width, height, radius, offset)
        hung.append(Pos(seat.station + offset, 0.0, middle) * (Rot(0.0, -90.0, 0.0) * flat))
    return hung


def parts() -> dict[str, Part]:
    """Every piece, named and in its assembled place."""
    lines = hull_lines.load()
    seat = rigging.step(HULL, lines, RIG)
    sails = _hung_sails(lines, seat)
    return {
        "hull": rigging.fit_mast(build(HULL, lines), HULL, lines, RIG),
        "mast": _stepped_mast(lines, seat),
        "course": sails[0],
        "topsail": sails[1],
    }


def model() -> Compound:
    """Everything as one shape, so `just preview` can render it."""
    return Compound(children=list(parts().values()))


def main() -> None:
    assembled = parts()
    box = Compound(children=list(assembled.values())).bounding_box()
    print(
        f"assembled {box.size.X:.0f} x {box.size.Y:.1f} x {box.size.Z:.1f} mm, "
        f"masthead {box.max.Z:.0f} mm above the baseline"
    )
    # Shown one by one rather than as a compound, so the viewer can colour them
    # apart and switch the sails off.
    for name, part in assembled.items():
        show_object(part, name=name)


if __name__ == "__main__":
    main()
