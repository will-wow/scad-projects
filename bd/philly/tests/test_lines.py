"""The lines plan read out of the DXF.

These pin the extraction against the documented boat, so a redraw in LibreCAD
that changes a layer name or splits a curve differently fails here rather than
silently producing a different hull.
"""

from __future__ import annotations

import numpy as np
import pytest

import lines as hull_lines

FOOT_MM = 304.8


def test_matches_the_documented_boat(lines):
    """Beam is the strongest check available: the scan agrees with the record."""
    assert lines.beam == pytest.approx(4620.1, abs=5.0)  # documented 15ft 2in
    assert lines.length / FOOT_MM == pytest.approx(53.8, abs=0.5)  # sources say 53-54ft
    assert lines.depth / FOOT_MM == pytest.approx(5.9, abs=0.3)  # scan: keel to rail


def test_curves_run_bow_to_stern(lines):
    for curve in (
        lines.sheer_half_width,
        lines.chine_half_width,
        lines.sheer_height,
        lines.chine_height,
    ):
        assert len(curve.x) >= 2
        assert np.all(np.diff(curve.x) > 0), "stations must increase, with no duplicates"


def test_closing_lines_are_not_read_as_hull_lines(lines):
    """The stem and transom verticals close the outline; they are not the curve.

    Reading them leaves two half-widths at one station, which came out as the
    stern tapering to a point instead of ending in a transom.
    """
    sheer = lines.sheer_half_width
    assert sheer.y[-1] > 50.0, "the stern should end in a transom, not a point"
    assert sheer.y[0] > 0.0, "the bow should end in a stem of some width"


def test_sheer_is_above_the_chine_everywhere(lines):
    """A station where the rail is below the bottom would loft inside out."""
    low, high = lines.sheer_half_width.span
    x = np.linspace(low, high, 200)
    assert np.all(lines.sheer_height.at(x) > lines.chine_height.at(x))
    assert np.all(lines.sheer_half_width.at(x) >= lines.chine_half_width.at(x))


def test_sampling_clamps_rather_than_extrapolating(lines):
    """Off the end of a curve, hold the end value.

    The curves cover slightly different spans, and a sheer rising steeply at
    the stern would run away if its last segment were extended.
    """
    curve = lines.sheer_height
    low, high = curve.span
    assert curve.value(low - 5000.0) == pytest.approx(float(curve.y[0]))
    assert curve.value(high + 5000.0) == pytest.approx(float(curve.y[-1]))


def test_the_document_is_parsed_once(lines):
    """load() reads four layers; it should not re-parse the file for each."""
    assert hull_lines._document() is hull_lines._document()
