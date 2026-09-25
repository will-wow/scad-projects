"""Shared fixtures.

Building a hull costs about a second, so the expensive ones are session-scoped
and shared: these tests assert about geometry, not about rebuilding it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lines as hull_lines  # noqa: E402
from hull import Deck, HullSpec, build  # noqa: E402

# Few sections: these tests are about whether the geometry is right, and the
# cavity ends are solved rather than sampled, so a coarse hull is the same hull.
STATIONS = 12

# The model's own layout: a forecastle, a middle platform and a quarterdeck,
# stepping down from bow to stern, with the bilge open between them.
DECKS = (
    Deck(0.0, 7 / 24, 0.50),
    Deck(9 / 24, 15 / 24, 0.40),
    Deck(17 / 24, 1.0, 0.20),
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
