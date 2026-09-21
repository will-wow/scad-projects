# Building a boat hull in build123d

A tour of how this model works, for someone who wants to modify it or build a
hull of their own. It assumes you can read Python and have build123d installed,
but not that you know CAD.

Everything here lives in [`bd/philly/`](.). The interesting files are
[`lines.py`](lines.py) (the data), [`hull.py`](hull.py) (the solid), and
[`main.py`](main.py) (the knobs). The rest is tooling.

## The shape of the problem

A boat hull sounds like it needs free-form surfaces. It doesn't — not this one.
The Philadelphia is a **hard-chine scow**: a flat bottom, a hard corner where
the bottom meets the side (the *chine*), and sides that flare up to the rail
(the *sheer*). Cut it anywhere across its width and you get a simple closed
outline. Stack enough of those outlines along the length, skin them, and you
have a hull.

That reduces the whole model to five steps:

```
DXF curves  ->  a section at any x  ->  loft  ->  subtract a cavity  ->  scale
```

Each step is one function. There is no compound-curved surface anywhere, no
NURBS patch, no surface modelling at all.

### A note on build123d's two dialects

build123d offers a *builder* API (`with BuildPart() as p:` and context
managers) and a *direct*, algebraic one (objects and operators). This code uses
the direct one throughout: shapes are values you pass around, and `-` means
subtract.

```python
hull = loft(faces)
hollowed = hull - cavity
```

For code that computes its geometry — loops, numpy, helper functions returning
faces — the direct API stays out of the way. The builder API shines when you're
writing something closer to a recipe. Don't feel obliged to pick the one the
tutorials use.

## Part 1: the data

A hull is traditionally described by a **lines plan**: two 2D views of the same
boat, from which the 3D shape is recovered.

- The **half-breadth plan** looks down from above and gives *half-widths* — how
  far from the centreline the boat is at each point along its length.
- The **profile** looks from the side and gives *heights* above the baseline.

Two lines matter here, each appearing in both views, so four curves in total:

| | half-width | height |
| --- | --- | --- |
| **sheer** (the rail) | `FAIR_TOP` | `FAIR_SHEER_PROFILE` |
| **chine** (bottom corner) | `FAIR_BOTTOM` | `FAIR_BASE_PROFILE` |

Those are DXF layer names in
[`designs/philadelphia_hull_lines.dxf`](designs/philadelphia_hull_lines.dxf),
drawn in LibreCAD over a photogrammetry scan. [`lines.py`](lines.py) reads them
with `ezdxf`, flattens splines into points, and hands back four curves:

```python
@dataclass(frozen=True)
class HullLines:
    sheer_half_width: Curve
    chine_half_width: Curve
    sheer_height: Curve
    chine_height: Curve
```

The profile view is drawn below the plan view so the two don't overlap on the
page, so reading it subtracts a fixed offset to recover true heights
(`PROFILE_OFFSET`). That's a drafting convention, not geometry.

### Curves that clamp rather than extrapolate

[`Curve`](lines.py#L46) is deliberately dumb — sorted samples and
`np.interp`:

```python
def value(self, x: float) -> float:
    """Sample at a single station, clamped as `at` is."""
    return float(np.interp(min(max(x, self.x[0]), self.x[-1]), self.x, self.y))
```

The clamping is the part worth copying. The four curves don't span exactly the
same range — hand-drawn curves never do — and a linear extrapolation off the
end of a sheer that is rising steeply runs away fast. Holding the end value
costs a fraction of a millimetre at the very tip and cannot explode.

**If you're drawing your own DXF**, the one rule that bit hardest: a line with
no run in X (a vertical closing line across the stem or transom) is not part of
a fore-and-aft curve, and including it gives you two different half-widths at
one station. [`read_layer`](lines.py#L95) drops those explicitly.

## Part 2: one section

Here is the heart of it. Given the four curves and a station `x`, build the
outline of the hull there:

```python
def _section(lines: HullLines, x: float, bulge: Bulge | None = None):
    y_sheer = lines.sheer_half_width.value(x)
    z_sheer = lines.sheer_height.value(x)
    y_chine = lines.chine_half_width.value(x)
    z_chine = lines.chine_height.value(x)

    if y_chine <= 1e-6 or y_sheer < y_chine or z_sheer <= z_chine:
        return None

    starboard = _side_profile(y_chine, z_chine, y_sheer, z_sheer, bulge)
    points = [(x, -y, z) for y, z in reversed(starboard)] + [(x, y, z) for y, z in starboard]
    return make_face(Polyline(*points, close=True))
```

Four things to notice:

1. **Only the starboard half is computed**, then mirrored by negating `y` and
   reversing. A boat is symmetric; say so once.
2. **`make_face(Polyline(*points, close=True))`** is the whole of the
   CAD. `Polyline` takes points and gives you a wire; `make_face` skins a
   planar closed wire. If your points are planar and in order, this always
   works.
3. **The section is closed across the top.** There is no notch for the deck.
   The outline runs up one side, straight across where the deck will be, and
   down the other. Opening it up is a later step, and doing it by subtraction
   rather than by construction is much easier to get right.
4. **Returning `None` is normal.** At the very bow the half-width goes to zero
   and there is no outline to build. The caller filters those out rather than
   treating it as an error.

### Where the side isn't straight

A straight chine-to-rail line makes the hull read as a flat-panelled box. Real
topsides swell outward. [`Bulge`](hull.py#L55) adds that with one parameter:

```python
def _side_profile(y_chine, z_chine, y_sheer, z_sheer, bulge):
    if bulge is None:
        return [(y_chine, z_chine), (y_sheer, z_sheer)]
    run = y_sheer - y_chine
    rise = z_sheer - z_chine
    chord = float(np.hypot(run, rise))
    return [
        (y_chine + run * t + bulge.at(t) * bulge.amount * chord, z_chine + rise * t)
        for t in (float(v) for v in np.linspace(0.0, 1.0, SIDE_SAMPLES))
    ]
```

Walk `t` from the chine (0) to the rail (1), and push each point out of the
straight chord by a smooth hump:

```python
def at(self, t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return float(np.sin(np.pi * t ** (np.log(0.5) / np.log(self.peak))))
```

That's a half-sine with its argument warped so the maximum lands at `peak`
rather than at the middle. Warping the *argument* rather than the value keeps
`at(0) == at(1) == 0` however far you move the peak — so the chine and the rail
stay exactly where the lines plan puts them, and only the middle moves. It's a
useful trick for any "bulge this edge" parameter.

`amount` is a **fraction of the side's own slant height**, not a millimetre
count. Near the bow the sections are small, and a fixed offset there would
swamp them; a fraction tapers automatically.

Two non-obvious constraints, both of which cost real debugging time:

- **The displacement is horizontal, not along the surface normal.** They look
  nearly identical (they differ by a `1/cos(flare)` stretch), but a horizontal
  one keeps every point at the height it started at. That property is what
  lets the cavity follow the same swell in Part 4.
- **Every station returns the same number of points.** Lofting between sections
  whose vertices don't correspond forces OCCT to build a common
  parameterisation, and that cost *sixty times* as much here. Keep your section
  outlines structurally identical and vary only the numbers.

## Part 3: the loft

With a section available at any `x`, the outer hull is three lines:

```python
stations = _station_positions(x0, x1, spec.stations)
faces = [f for f in (_section(lines, float(x), spec.bulge) for x in stations) if f is not None]
hull = loft(faces)
```

`loft` skins a list of planar faces in order and caps the ends. That's it —
that's the hull.

Stations are **cosine-spaced** rather than evenly spaced:

```python
def _station_positions(x0: float, x1: float, count: int) -> np.ndarray:
    """Cosine-spaced stations: dense at the ends, sparse amidships."""
    t = np.linspace(0.0, 1.0, count)
    return x0 + (x1 - x0) * (1.0 - np.cos(t * np.pi)) / 2.0
```

Hull curvature is concentrated at the bow and stern; amidships the shape barely
changes over long stretches. Cosine spacing puts samples where the shape is
doing something. It's the same reasoning behind Chebyshev nodes, and it applies
to almost any swept shape with busy ends.

`stations` is purely a smoothness/speed dial — 12 while you're iterating, 48
for export. Nothing about the hull's dimensions depends on it, which is a
property worth protecting (see Part 6).

## Part 4: hollowing, by lofting a second solid

The obvious way to hollow a solid is an offset/thick-solid operation. This code
doesn't use one. Instead it **lofts a second, smaller solid and subtracts it**:

```python
return _as_part(hull - loft(faces), "cavity subtraction")
```

This is faster by an order of magnitude, and it sidesteps a whole bug class:
a thick-solid operation needs to be told which face to leave open, and "the
deck" is surprisingly hard to identify reliably. Building the cavity so that it
pokes out through the top means the deck opens *by construction* — there is no
face to choose.

The catch is getting the inset right, and this is the one piece of real
geometry in the project. Offsetting a trapezoid is not the same as shrinking
it:

```python
# Inward normal of the side, and the side's own direction.
base_y = y_chine - wall * rise / length
base_z = z_chine + wall * run / length

# Where the offset side meets the offset floor.
bottom = z_chine + wall
floor_z = bottom if floor_z is None else max(floor_z, bottom)
s_floor = (floor_z - base_z) * length / rise
floor_y = base_y + s_floor * run / length
```

The floor moves straight up by `wall`. The flared side has to move
**perpendicular to itself**. The new chine corner is where those two offset
lines *intersect* — not either endpoint moved by a fixed amount. Move the
corner straight inward instead and a 2mm request measures 2.8mm of side wall,
because the side's lean turns a horizontal offset into a smaller perpendicular
one.

If you take one thing from this file, take that: **offsetting a polygon is
about offsetting its edges and re-intersecting them**, never about moving its
vertices.

The cavity is also carried one wall thickness *above* the rail
(`top_z = z_sheer + wall`), which is what makes the subtraction remove the
section's closed top edge and leave an open boat.

## Part 5: decks, wells and bulwarks

The real boat isn't one continuous open cavity: it's decked at the bow, has an
open slice, a decked middle, another open slice, then a decked quarterdeck.

That's described declaratively in [`main.py`](main.py):

```python
open_spans = (
    (
        OpenSpan(7 / 24, 9 / 24),
        OpenSpan(15 / 24, 17 / 24),
    ),
)
bulwark = (10.0,)
```

Spans are fractions of the overall length. [`_decked`](hull.py#L384) computes
the complement — every stretch the open spans leave over — and
[`_hollow`](hull.py#L427) makes one subtraction per region, with a different
floor height for each:

```python
for span in spec_spans:
    hollowed = _cut(..., lambda x, lift=lift: lines.chine_height.value(x) + wall + lift)

for stretch in _decked(spec_spans):
    hollowed = _cut(..., deck_height)
```

The trick that makes decks cheap: a **deck is just a cavity with a raised
floor**. Put the cavity's bottom part-way up and the hull's own sides carry on
past it as bulwarks, for free. No separate deck surface, no lids, no extra
booleans.

And the deck follows the sheer rather than sitting at a fixed height:

```python
def deck_height(x: float) -> float:
    return lines.sheer_height.value(x) - drop
```

A fixed drop below the rail means the deck rises toward bow and stern with the
sheer, which is what boats do. Measuring it as a fraction of local depth
instead makes the forecastle climb faster than the sheer, because the forefoot
sweeps up underneath it.

Each `loft` caps its own ends, so **every cut leaves a bulkhead** where it
stops. You get transverse structure without modelling any.

## Part 6: the guardrails

Roughly a fifth of `hull.py` exists to catch silent failures, because every
failure this model has had looked completely fine from the outside. A hull that
was never hollowed, a deck left skinned over — both are valid solids of
plausible volume. Three patterns are worth stealing.

**Probe the inside, not the outside.** [`_assert_open`](hull.py#L231) checks
that the open spans are actually open by asking whether a point is solid:

```python
z = lines.sheer_height.value(x) - 0.5 * wall
if hull.is_inside(Vector(x, 0.0, z)):
    raise RuntimeError(f"the span {span.start:.2f}..{span.end:.2f} is still decked over")
```

`is_inside` is the cheapest correctness check in CAD. Note the probe is aimed
*inside the band the deck skin would occupy* — a probe lower down finds air
whether or not the deck was removed, which is a test that always passes.

**Solve for geometry rather than sampling it.** Near the stem the hull is
narrower than two walls, so the cavity has to stop and leave the ends solid.
Letting that happen wherever the stations land makes the solid plugs an
artefact of the station count — the bow plug varied from 812mm to 1566mm purely
with `stations`, quietly changing print weight. [`_cavity_span`](hull.py#L341)
bisects for the true boundary instead:

```python
def holds_cavity(x: float) -> bool:
    return _inner_section(lines, x, wall) is not None
```

Now `stations` controls smoothness and nothing else.

**Narrow the result of every boolean.** build123d's operators are generic over
shape kinds, so a degenerate operation hands back something that isn't a solid
rather than raising. [`_as_part`](hull.py#L201) insists:

```python
if len(solids) == 1 and isinstance(shape, Part):
    return shape
largest = max(solids, key=lambda s: s.volume)
debris = sum(s.volume for s in solids if s is not largest)
if debris > DEBRIS_FRACTION * largest.volume:
    raise RuntimeError(f"{what} split the hull into {len(solids)} pieces; ...")
```

Booleans against curved surfaces legitimately shed microscopic slivers, so
those are discarded — but only after checking they really are dust. Taking the
largest piece unconditionally would turn "the cavity escaped through the side
and cut the boat in two" into a quiet success.

The same instinct runs through [`tests/`](tests): assertions measure the built
solid (volumes, wall thicknesses, probe points, tessellated face normals)
rather than checking that the code ran.

## Part 7: units, and scaling exactly once

The DXF is in real-world millimetres — a 16.4m boat. The toy is 300mm. The
conversion happens **once, at the very end**:

```python
factor = spec.length / lines.length
...
return _as_part(scale(hull, factor), "scaling")
```

Everything upstream works in source units, and anything expressed in finished
millimetres (`wall`, `bulwark`, `OpenSpan.floor`) is divided by `factor` on the
way in. Mixing the two is a rich source of bugs — a wall that's 55× too thick
produces a completely solid hull that looks fine until you weigh it.

## Part 8: the surrounding tooling

Not part of the model, but most of what makes it pleasant to work on. All
driven by [`justfile`](justfile).

- **[`watch.py`](watch.py)** — `just watch`. Keeps build123d imported between
  reloads, so a save repaints in ~0.2s instead of paying a ~16s cold import
  each time. It watches *directories*, not files (atomic saves replace inodes,
  so a file watch goes deaf after one save), and sets
  `sys.dont_write_bytecode = True` because `.pyc` files are validated by
  whole-second mtime plus size — edit a file twice in one second without
  changing its length and you'll silently run stale code.
- **[`preview.py`](preview.py)** — `just preview`. A headless renderer that
  tessellates the part and paints it into an SVG, for sessions with no browser.
  It's model-agnostic: `--model module:callable`.
- **[`export.py`](export.py)** — `just build`. Writes 3MF via `lib3mf`, which
  records the unit so the slicer doesn't guess. It welds the tessellation
  first: OCCT meshes each face independently, so a shared edge arrives as two
  sets of vertices and the result reads as non-manifold. It refuses to write a
  mesh that's still non-manifold after welding.

One pattern worth reusing: both `watch` and `preview` set a `PREVIEW`
environment variable, which the model reads:

```python
stations = (12 if preview_mode() else 48,)
```

The model decides what to trade. Because `stations` only affects smoothness,
the shape you judge in the loop is the real one.

## Making your own hull

If you want to do this for a different boat:

1. **Draw four curves** in DXF over your reference — sheer and chine, each in
   half-breadth and profile. Keep them single-valued in X. Put stem and transom
   closing lines on their own layer or omit them.
2. **Point [`lines.py`](lines.py) at your layer names** and set `PROFILE_OFFSET`
   to however far apart you drew the two views.
3. **Set the spec** in [`main.py`](main.py): `length`, `wall`, `open_spans`,
   `bulwark`, `bulge`.
4. **Run `just watch`** and tune by eye.

If your boat has a *rounded* bilge rather than a hard chine, `_side_profile` is
the place to change — it's the only function that decides what a section looks
like between its corners. Everything downstream just consumes points.

If your boat has genuine tumblehome (topsides curving back inward), `Bulge`
won't express it, and you'd want per-station section data. The architecture
takes that without much disruption: keep the four curves as the *envelope* and
add a normalized offset-from-chord function interpolated between drawn
stations. `_side_profile` stays the only thing that changes.

## Reference

| File | What it does |
| --- | --- |
| [`lines.py`](lines.py) | DXF → four faired curves |
| [`hull.py`](hull.py) | sections → loft → hollow → scale |
| [`main.py`](main.py) | the spec, and `model()` for the viewer |
| [`export.py`](export.py) | 3MF/STL/STEP out |
| [`preview.py`](preview.py) | headless SVG/PNG renderer |
| [`watch.py`](watch.py) | warm-process live reload |
| [`tests/`](tests) | geometry assertions |
| [`PRINTING.md`](PRINTING.md) | slicer settings, flotation, ballast |

Line links point at the current commit and will drift; the function names are
the durable part.
