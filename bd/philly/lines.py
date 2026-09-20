"""Read the hull lines plan out of the DXF and turn it into sampled 3D edges.

The DXF (`designs/philadelphia_hull_lines.dxf`) holds two 2D views of the same
hull, both with X = distance aft of the bow, in real millimetres:

- Plan view, near Y = 0 and up: half-width from the centreline. `FAIR_T` is the
  sheer (rail) and `FAIR_BOTTOM` the chine (where the flat bottom meets the
  side). These are the hand-faired curves -- a chain of LINEs plus one SPLINE
  each -- and supersede the raw `SHEER_TOP` / `CHINE_BOTTOM` polylines.
- Profile view, shifted down by PROFILE_OFFSET so it doesn't overlap the plan:
  height above the keel baseline. `SHEER_PROFILE` is the rail height and
  `BASE_PROFILE` the bottom's rocker, which for a flat-bottomed hull is also
  the chine's height.

The profile curves have not been faired by hand, so they are still raw scan
output and carry obvious artefacts: an 871mm spike at the first station of
`BASE_PROFILE`, a 250-year-old transom confusing the last few stations of both.
`fair()` rejects those the same way a person would -- points that disagree with
their neighbours -- then smooths what's left.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from ezdxf.entities.lwpolyline import LWPolyline
from ezdxf.entities.spline import Spline
from ezdxf.filemanagement import readfile
from scipy.interpolate import UnivariateSpline

DXF_PATH = Path(__file__).parent / "designs" / "philadelphia_hull_lines.dxf"

# The profile view is drawn this far below the plan view; subtract to recover
# true height above the baseline.
PROFILE_OFFSET = -3200.0

# Flattening tolerance when sampling SPLINE entities, in mm at 1:1.
SPLINE_TOLERANCE = 2.0


@dataclass(frozen=True)
class Curve:
    """A 2D curve as sorted samples, X strictly increasing."""

    x: np.ndarray
    y: np.ndarray

    def at(self, x: np.ndarray) -> np.ndarray:
        """Sample at each of `x`, holding the end values rather than extrapolating.

        Clamping matters at the bow and stern: the plan and profile curves cover
        slightly different spans, and a linear extrapolation off the end of a
        sheer that is rising steeply would run away.
        """
        return np.interp(np.clip(x, self.x[0], self.x[-1]), self.x, self.y)

    def value(self, x: float) -> float:
        """Sample at a single station, clamped as `at` is."""
        return float(np.interp(min(max(x, self.x[0]), self.x[-1]), self.x, self.y))

    @property
    def span(self) -> tuple[float, float]:
        return float(self.x[0]), float(self.x[-1])


def _sorted_unique(points: list[tuple[float, float]]) -> Curve:
    """Order samples by X and drop duplicate stations.

    The faired layers are drawn as several entities that meet end to end, so
    joints appear twice and the pieces arrive in no particular order. Every
    curve here is single-valued in X (they run bow to stern), so sorting is
    enough to chain them -- no need to match endpoints.
    """
    ordered = sorted(points)
    x_out: list[float] = []
    y_out: list[float] = []
    for x, y in ordered:
        if x_out and x - x_out[-1] < 1e-6:
            continue
        x_out.append(x)
        y_out.append(y)
    return Curve(np.array(x_out), np.array(y_out))


def read_layer(layer: str, *, y_offset: float = 0.0) -> Curve:
    """Collect every LINE / LWPOLYLINE / SPLINE on `layer` into one curve."""
    doc = readfile(str(DXF_PATH))
    points: list[tuple[float, float]] = []
    for entity in doc.modelspace().query(f"*[layer=='{layer}']"):
        kind = entity.dxftype()
        if kind == "LINE":
            start, end = entity.dxf.start, entity.dxf.end
            if abs(float(start[0]) - float(end[0])) < 1e-6:
                # A segment with no run in X is a closing line across the stem or
                # the transom, drawn to shut the half-outline against the
                # centreline. It is not part of the fore-and-aft curve, and
                # keeping it would leave two values at one station -- which reads
                # as the stern tapering to a point instead of ending in a transom.
                continue
            points += [
                (float(start[0]), float(start[1]) - y_offset),
                (float(end[0]), float(end[1]) - y_offset),
            ]
        elif isinstance(entity, LWPolyline):
            points += [(float(p[0]), float(p[1]) - y_offset) for p in entity.get_points()]
        elif isinstance(entity, Spline):
            points += [
                (float(p[0]), float(p[1]) - y_offset)
                for p in entity.flattening(distance=SPLINE_TOLERANCE)
            ]
    if not points:
        raise ValueError(f"no geometry found on layer {layer!r} in {DXF_PATH}")
    return _sorted_unique(points)


def fair(
    curve: Curve,
    *,
    trim_head: int = 0,
    trim_tail: int = 0,
    window: int = 7,
    tolerance: float = 4.0,
    smooth: float = 150.0,
) -> Curve:
    """Stand in for the hand-fairing the profile curves never got.

    Two different problems, so two different tools. The artefacts at the ends are
    documented in the handoff -- an 871mm spike where the scan lost the damaged
    bow, a transom that confused the "local top" search for the last stations --
    and a statistical filter is the wrong way to remove them, because the ends of
    a sheer are also where it genuinely rises fastest. Rejecting "points that
    disagree with their neighbours" there throws away the bow's sheer rise, which
    is a real feature of this hull. So the ends are trimmed by count, per the
    handoff, and whatever survives anchors the curve.

    Spikes in the interior are fair game for a Hampel filter: a point is rejected
    when it sits more than `tolerance` robust standard deviations from the median
    of the window around it. `smooth` is the residual budget, in mm^2 per point,
    for the spline that then smooths the remainder.
    """
    x = curve.x[trim_head : len(curve.x) - trim_tail if trim_tail else None]
    y = curve.y[trim_head : len(curve.y) - trim_tail if trim_tail else None]

    half = window // 2
    keep = np.ones(len(y), dtype=bool)
    # Endpoints are excluded: they have no symmetric window, and after trimming
    # they are the anchors for the bow and stern.
    for i in range(1, len(y) - 1):
        lo, hi = max(0, i - half), min(len(y), i + half + 1)
        neighbours = np.delete(np.arange(lo, hi), np.where(np.arange(lo, hi) == i))
        if len(neighbours) < 3:
            continue
        median = np.median(y[neighbours])
        # 1.4826 * MAD estimates sigma for normally distributed noise.
        sigma = 1.4826 * np.median(np.abs(y[neighbours] - median))
        if sigma > 0 and abs(y[i] - median) > tolerance * sigma:
            keep[i] = False

    x_kept, y_kept = x[keep], y[keep]
    if len(x_kept) < 4:
        return Curve(x_kept, y_kept)
    spline = UnivariateSpline(x_kept, y_kept, s=smooth * len(x_kept), k=3)
    return Curve(x_kept, np.asarray(spline(x_kept), dtype=float))


@dataclass(frozen=True)
class HullLines:
    """The four curves, faired, in real millimetres at 1:1."""

    sheer_half_width: Curve
    chine_half_width: Curve
    sheer_height: Curve
    chine_height: Curve

    @property
    def length(self) -> float:
        """Overall length, bow to the aft end of the sheer."""
        return self.sheer_half_width.span[1]

    @property
    def beam(self) -> float:
        return 2.0 * float(self.sheer_half_width.y.max())

    @property
    def depth(self) -> float:
        return float(self.sheer_height.y.max())


def load() -> HullLines:
    """Read the DXF and return the faired lines plan.

    The plan-view curves are taken as drawn -- they are the hand-faired ones.
    The profile curves are still raw, so they get `fair()` applied.
    """
    return HullLines(
        sheer_half_width=read_layer("FAIR_T"),
        chine_half_width=read_layer("FAIR_BOTTOM"),
        # trim_tail=3: the last three stations read 1800, 1803, 1504 -- the
        # transom, not the sheer.
        sheer_height=fair(read_layer("SHEER_PROFILE", y_offset=PROFILE_OFFSET), trim_tail=3),
        # trim_head=4: an 871mm spike, then three near-zero readings where the
        # scan lost the bottom at the bow. trim_tail=1: a 339mm jump at the transom.
        chine_height=fair(
            read_layer("BASE_PROFILE", y_offset=PROFILE_OFFSET), trim_head=4, trim_tail=1
        ),
    )


if __name__ == "__main__":
    lines = load()
    print(f"LOA  {lines.length:8.1f} mm   ({lines.length / 304.8:.2f} ft)")
    print(f"beam {lines.beam:8.1f} mm   ({lines.beam / 304.8:.2f} ft)")
    print(f"depth{lines.depth:8.1f} mm   ({lines.depth / 304.8:.2f} ft)")
    for name, curve in (
        ("sheer half-width", lines.sheer_half_width),
        ("chine half-width", lines.chine_half_width),
        ("sheer height", lines.sheer_height),
        ("chine height", lines.chine_height),
    ):
        lo, hi = curve.span
        print(
            f"  {name:17} {len(curve.x):3} pts  X[{lo:8.1f},{hi:8.1f}]  "
            f"Y[{curve.y.min():7.1f},{curve.y.max():7.1f}]"
        )
