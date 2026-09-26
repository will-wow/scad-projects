"""Shared fixtures.

Building a hull costs about a second, so the expensive ones are session-scoped
and shared: these tests assert about geometry, not about rebuilding it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from build123d import Compound, Part

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lines as hull_lines  # noqa: E402
from hull import Deck, HullSpec, build  # noqa: E402


def steepest_overhang(part: Part | Compound) -> float:
    """How far the worst downward-facing surface leans, as a sine.

    Compare against sin(max_overhang). Measured on the exact surfaces rather
    than a mesh, because a tessellated cone's flat facets lean a little steeper
    than the cone does and would fail a chamfer drawn at exactly the limit. The
    samples stay off the edges of each face's parameter range, where a sphere's
    pole has no well-defined normal, and faces on the bed are skipped: the bed
    cannot overhang.
    """
    samples = np.linspace(0.02, 0.98, 25)
    return max(
        -face.normal_at(u, v).Z
        for face in part.faces()
        for u in samples
        for v in samples
        if face.position_at(u, v).Z > 1e-6
    )


# Few sections: these tests are about whether the geometry is right, and the
# cavity ends are solved rather than sampled, so a coarse hull is the same hull.
STATIONS = 12

# The model's own layout: a forecastle, a middle platform and a quarterdeck,
# stepping down from bow to stern, with the bilge open between them.
DECKS = (
    Deck(0.0, 0.31, 0.48),
    Deck(0.39, 0.655, 0.34),
    Deck(0.71, 1.0, 0.30),
)


@pytest.fixture(scope="session")
def lines():
    return hull_lines.load()


@pytest.fixture(scope="session")
def open_hull(lines):
    """Hollow for its whole length, no deck."""
    return build(HullSpec(stations=STATIONS), lines)


@pytest.fixture(scope="session")
def solid_hull(lines):
    """No cavity at all -- the outer loft on its own."""
    return build(HullSpec(stations=STATIONS, wall=0.0), lines)


@pytest.fixture(scope="session")
def decked_hull(lines):
    """Three platforms at three heights, bilge open between them."""
    return build(HullSpec(stations=STATIONS, decks=DECKS), lines)
