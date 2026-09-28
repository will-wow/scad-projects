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

The drawing also runs from the transom: its X increases going forward. The
model wants X to be the distance aft of the bow, so [`load`](lines.py) mirrors
all four curves about the same point -- the two ends of the sheer -- which
keeps them aligned with one another. A test pins the result against the scan:
two metres from the bow the hull is wider and lower than two metres from the
transom.

### Curves that clamp rather than extrapolate

[`Curve`](lines.py#L46) is deliberately dumb — sorted samples and
`np.interp`:

```python
def value(self, x: float) -> float:
    """Sample at a single station, clamped as `at` is."""
    return float(np.interp(x, self.x, self.y))
```

The clamping is the part worth understanding, and it is free: **`np.interp`
never extrapolates.** Its `left` and `right` parameters default to the first
and last values of `y`, so anything off either end comes back as the end value.
Those parameters exist to *override* that, not to switch it on.

That happens to be exactly what a lines plan wants. The four curves don't span
quite the same range — hand-drawn curves never do — so stations near either
end genuinely do fall off the end of one curve or another, and a linear
extrapolation off a sheer that is rising steeply runs away fast. Holding the
end value costs a fraction of a millimetre at the very tip and cannot explode.

It is worth knowing this is deliberate, because the alternative is to not
notice: if you ever want to *find* the stations that fall off the end rather
than quietly clamp them, pass `left=np.nan, right=np.nan` and they become
visible.

**If you're drawing your own DXF**, the one rule that bit hardest: a line with
no run in X (a vertical closing line across either end) is not part of
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
4. **Returning `None` is normal.** At the very ends the hull narrows to almost
   nothing and there is no outline to build. The caller filters those out rather than
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
count. Near the ends the sections are small, and a fixed offset there would
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

Hull curvature is concentrated at the two ends; amidships the shape barely
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

## Part 5: decks and bulwarks

The real boat isn't one continuous open cavity: it carries three platforms — a
forecastle, a middle platform and the quarterdeck — at three different heights,
with the bilge open between them. All three are measured off the Smithsonian's
scan of the surviving boat.

That's described declaratively in [`main.py`](main.py):

```python
decks = (
    (
        Deck(0.0, 0.31, 0.48),
        Deck(0.39, 0.655, 0.34),
        Deck(0.71, 1.0, 0.30),
    ),
)
```

`start` and `end` are fractions of the overall length; `height` is a fraction
of the hull's depth, measured up from the bottom. Anything no deck covers is
hollowed right down to the inside of the bottom, so the gaps don't need
declaring — [`open_stretches`](hull.py) computes the complement.

The trick that makes decks cheap: a **deck is just a cavity with a raised
floor**. Put the cavity's bottom part-way up and the material below it is the
platform, while the hull's own sides carry on past it as bulwarks — for free.
No separate deck surface, no lids, no extra booleans.

```python
for stretch in open_stretches(ordered):
    hollowed = _cut(..., lambda x: lines.chine_height.value(x) + wall)

for deck in ordered:
    floor = deck.height * lines.depth
    hollowed = _cut(..., lambda x, floor=floor: floor)
```

Both loops call the same `_cut`. The only difference is where the floor goes —
which is why there's one concept here and not two. A shallow well that
shouldn't reach the bottom is just a low deck.

Note `lambda x, floor=floor: floor`. Binding the loop variable as a default
argument matters: a bare closure over `floor` would see whatever the variable
held when the lambda was finally called. It happens to be safe here because
`_cut` runs immediately, but it's the kind of thing that's safe until someone
makes the call lazy.

Each `loft` caps its own ends, so **every cut leaves a bulkhead** where it
stops. You get transverse structure without modelling any.

Overlapping decks are refused rather than merged. Two heights over one stretch
has no sensible answer, and picking one quietly is worse than saying so.

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

**Solve for geometry rather than sampling it.** Near each end the hull is
narrower than two walls, so the cavity has to stop and leave the ends solid.
Letting that happen wherever the stations land makes the solid plugs an
artefact of the station count — a plug's length moves by the better part of a
metre (full size) purely with `stations`, quietly changing print weight. [`_cavity_span`](hull.py#L341)
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
return as_part(scale(hull, factor), "scaling")
```

Everything upstream works in source units, and anything expressed in finished
millimetres (`wall`) is divided by `factor` on the
way in. Mixing the two is a rich source of bugs — a wall that's 55× too thick
produces a completely solid hull that looks fine until you weigh it.

## Part 8: the surrounding tooling

Not part of the model, but most of what makes it pleasant to work on. All
driven by [`justfile`](justfile).

- **[`assembly.py`](assembly.py)** — what `just watch` opens by default: the
  boat with its rig standing in it. See Part 10.
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

## Part 9: the rig

[`rig.py`](rig.py) adds the mast, and it is the one part of the project that
uses build123d's primitives -- `Box`, `Cylinder`, `RegularPolygon`, `extrude` --
rather than lofting sections. It also works in **finished millimetres**
throughout, unlike `hull.py`: the hull arrives already scaled, so this is the
far side of that line.

Three printed parts: the bar and tube, unioned into the hull; the mast, which
lifts out; and the sails, which clip onto the yards.

### The socket is derived, not written down

The mast stands in the forward well, and the well is wherever the decks are not:

```python
stretches = open_stretches(sorted(spec.decks, key=lambda d: d.start))
start, end = stretches[0]
```

Move a deck and the mast moves with it, instead of ending up buried in a
platform. This is why `hull.open_stretches` is public.

Everything else about the socket comes from the lines plan at that station --
the rail height, the chine, and `hull.inner_half_width`, which is the one place
that knows where the inside of a flared, bowed hull actually is. The bar is cut
to reach it:

```python
bar_half_length = inner_half_width(lines, source_x, wall, bar_top / factor, spec.bulge) * factor
```

Measured at the bar's **top**, because the side flares: the inside is widest
there, so the bar overlaps into the wall at its lower edge rather than leaving a
gap. The overlap is 0.73mm into a 2mm wall, and a test asserts the fitted hull
is no wider than the bare one -- which is what catches a bar that punches
through.

### Two constraints that are not obvious

**The bore must not reach the bottom.** It stops at the inside of the hull's
floor. A bore one millimetre longer is a hole in the boat.

**The tube runs all the way down**, which does two jobs. It steps the mast, and
it plants a pillar under the middle of the bar. Without it the bar is a single
78mm unsupported span to bridge, printed bottom-up; with it, two of 34.4mm.

### Why the mast is hexagonal

So it can print lying down. A round mast on the bed rolls and touches along a
line; a hexagon rests on a flat. The shaft is built standing up, because yard
heights are easier to reason about as z, then laid down as the last step:

```python
laid = Rot(0.0, 90.0, 0.0) * _upright_mast(spec, lines, rig)
```

That carries the shaft from +Z to +X and leaves the yards along Y, all in the
plane of the bed. The hexagon is drawn with `rotation=30` so that its *flats*
end up facing the bed rather than its corners -- a test measures the part's
height against the across-flats figure, which is the narrower of the two, so
getting this backwards fails rather than printing badly.

Only the base is round, for as long as the tube holds it, so the mast can turn.
Above that the hexagon is wider across its corners than the bore, which is what
stops it dropping through.

The yards follow the same logic and were got wrong first. Round, and thinner
than the mast, they sat on its centreline -- which left each one hanging 1.25mm
above the bed for its whole length, with nothing underneath. They
are now square and exactly as wide as the mast, so they lie on the bed with it:

```python
bar = Box(width, 2.0 * half, width)
bar = fillet(bar.edges().filter_by(Axis.Y), rig.yard_fillet)
```

A sail still needs something round to clip onto, so a short length near each tip
is turned down to a neck -- cut the square away, put a cylinder back:

```python
bar -= at * Box(2.0 * width, rig.clip_length, 1.2 * width)
bar += at * (lengthwise * Cylinder(radius, rig.clip_length))
```

That is a 2.5mm bridge with a square shoulder at each end rather than a
cantilever, and the shoulders double as what stops a sail sliding along the
yard. It also fixed something that was quietly broken: when the clip was a
shallow groove turned into a round yard, the groove's floor was *narrower* than
a sail's mouth, so nothing held the sail on at all. Clipping onto the full neck
diameter, the mouth has to spring over it.

### How long the yards are

Nothing in the record gives the yards, only the 36ft mast. Models of the boat
show the course's yard reaching past the rail on both sides, so its length is
set against the hull's beam rather than the mast -- `yard_beam = 1.10`, 10%
wider than the boat -- and moves with the hull:

```python
def course_yard(spec, lines, rig):
    return rig.yard_beam * lines.beam * (spec.length / lines.length)
```

The topsail's foot yard is the same length, so the two sails meet edge to edge,
and its head yard is `topsail_taper` (0.72) of that: the topsail narrows toward
the masthead. A sail is therefore a trapezoid, `sail(rig, foot, head, height,
...)`, with the eyes at its four corners; the course is just the case where foot
and head are equal.

### Sails clip on, and the corners are the whole problem

A sail is a 0.6mm plate. The yard is 2.5mm thick, and the hole has to be wider
still -- so a hole through the plate's edge would be wider than the plate. Each
corner therefore carries an eye on a short neck, which is what a real sail's
cringle is anyway.

The neck is not decoration. A sail spans the whole width of its yard and **the
mast stands in the middle of it**, so a plate hung straight off the yard's axis
tries to occupy the same space as the mast. The first assembled render showed
exactly that -- 130 cubic millimetres of sail inside the mast, a sail that could
never have been fitted. `stand_off` sizes the neck against the mast's
across-corners width, since the mast can turn in its socket:

```python
corners = mast_width(spec, lines) / np.sqrt(3.0)
return corners + rig.sail_thickness + rig.mast_clearance
```

The eye is as wide as its neck, so the corner rises off the bed as a wall with
a ring on top and nothing overhangs. Its mouth opens **upward** -- away from the
bed while printing, and square to the sail once rigged, so it presses onto both
yards at once. Mouths facing up on one yard and down on the other would need the
sail to stretch to reach both.

### Flush posts, patches and a bolt rope, because the posts snapped

The sail's size is measured between its eyes, and the plate used to be exactly
that shape, so each post stood centred on the plate's corner: three quarters of
it hung off the sail, held by a 0.6mm plate under one quarter of its base. In
play that plate folded right where it met the post whenever a sail was pulled
off, and PLA does not take much of that before it whitens and snaps.

Nothing needed the plate to stop at the eyes; only the eyes have to be on the
necks. So the plate is now the convex hull of the four posts (`_hull`), which
puts every post flush with both edges and wholly on the sail, and the sail's
head lies level with the top of its yard, where a real sail is laced on.

A real sail is also sewn double at its corners and roped round its edges, so
this one is too. Each eye gets a **patch** `patch_thickness` (1.6mm) thick, a
diamond `patch` (10mm) across from the eye, cut to the plate. A **bolt rope**
`rope_width` (1.5mm) wide and `rope_thickness` (1.2mm) thick runs round the
whole edge, tying the four posts together. Both are on the side away from the
bed, so they print as plain raised walls.

How thick they can be is set by what is above them once the sail is rigged. A
patch lies under the yard's square shoulder next to the neck, which comes to
within `stand_off - mast_width / 2` (2.0mm) of the bed. The rope also crosses in
front of the mast at the head and foot, and the mast's corners come to within
`sail_thickness + mast_clearance` (1.6mm). Each has to leave `TOLERANCE` clear,
and the tests check both.

`sails()` is the one builder here that deliberately does *not* go through
`as_part`: two sails really are two solids, so "more than one piece" is the
answer rather than the failure it would be anywhere else.

## Part 10: the assembled view

[`assembly.py`](assembly.py) exists because every part is modelled and exported
the way it wants to *print*, which means nothing in `dist/` shows what the boat
looks like. It stands the mast in its socket and hangs the sails on the yards:

```python
hung.append(Pos(seat.station - offset, 0.0, middle) * (Rot(0.0, 90.0, 0.0) * flat))
```

A sail is built lying down -- height along x, width along y, thickness along z
-- so rotating 90 degrees about y carries the height up to vertical, leaves the
width athwartships, and turns the plate to face fore and aft. The shift is
forward, not aft: a square sail's yard is slung ahead of the mast so the canvas
does not chafe on it.

This is a picture, not a part. Nothing here is manifold or printable, and
`just build` remains the thing that writes files.

It pays for itself anyway, because **putting the parts in one coordinate system
is the only way to ask whether they fit**. The test that matters is one line of
intent:

```python
shared = (assembled[first] & assembled[second]).volume
assert shared == pytest.approx(0.0, abs=1e-6)
```

Every pair of parts, no overlap. That is what caught the sails passing through
the mast, and it would catch it again.

## Part 11: the awning frame

[`awning.py`](awning.py) makes two more printed parts: a frame over the after
half that drops into sockets in the decks and lifts out again, and a canvas
that clips onto it.

**The frame is its legs.** It runs from the first pair of legs to the last, with
a crossbar over every pair, so both ends are closed and every crossbar stands on
something:

```python
nodes = (tuple((f.station, f.half) for f in feet),)
```

`Frame.bars` is just those stations. The rails and crossbars all stop at a
leg's centre, so each leg runs up to the bars' tops rather than to the roof's
middle plane -- otherwise every end corner would print with a notch in it.

**The canvas is a sail.** It is `rig.sail` again, cut to the frame instead of
the yards: its foot spans the necks on the first crossbar and its head the necks
on the last, which is narrower because the hull closes in toward the transom.
Only those two crossbars are necked, each neck just inboard of the rail with a
square shoulder between them. The necks are `rig.neck_radius` — the same number
the canvas's eyes were cut for, imported rather than copied.

It prints flat and eyes up, like the sails, and is rigged the other way up:
`rigged_canvas` gives it a half turn about y, which puts the plate on top, the
eyes' mouths facing down onto the necks, and the wider foot forward. Its plate
stands off its eyes only far enough to clear the bars' tops (`canvas_offset`);
the sails stand off further, but that is to clear the mast. Rigged that way up,
the patches and bolt rope hang under the plate, so it is the patches'
thickness, not the plate's, that has to clear the bars.

### Measure the hull where the leg actually is

A leg's offset comes from `hull.inner_half_width` **at the height of the deck it
stands on**, not at the rail:

```python
inside = inner_half_width(lines, at, spec.wall / factor, height / factor, spec.bulge)
```

The side flares outward going up, so the inside is narrowest down at the deck —
by about 3.5mm on the quarterdeck. Measuring at the rail would put the feet
through the planking. The hull also closes in fast toward the transom, so legs
too far aft pinch the frame to a point. The last pair stands at 0.895, just aft
of the quarterdeck's benches, which carries the frame nearly to the transom as
the museum's model does. The two pairs before it stand on the benches, and are
measured at the seat instead (see Part 13).

### A boss keeps the socket out of the bottom

The obvious thing is to bore the socket straight into the deck. But a deck is
modelled solid from the bottom up, so the floor of that socket is the boat's
bottom, below the waterline. On the quarterdeck there is 8.3mm of solid; a 5mm
socket would take most of it.

So each leg steps on a 3mm boss and the socket is bored into that, leaving over
6mm of floor. `fit_awning` refuses to build a frame whose sockets come within
2mm of the outside, and a test checks the same thing from the other end.

### The roof is planar on purpose

The sheer rises nearly 5mm toward the transom under the awning and the roof does
not follow it — the legs absorb it instead. That is what lets the part print **roof down**, with the
roof as one flat connected first layer and the legs rising off it as plain
columns. Following the sheer would leave one end of the roof standing 5mm off
the bed with its crossbar hanging in air.

The side rails are a polyline through the leg tops.

## Part 12: the guns

[`guns.py`](guns.py) puts three guns in the boat: the 12-pounder in the bow,
firing over the stem, and a 9-pounder either side amidships, staggered and
firing over the rail. The barrel, the carriage and the trunnion pin are in
[`cannon/`](cannon); this is what stands them on the decks.

### Why the carriage clips on rather than slides in

The first plan was a drawer: a dovetail foot under the carriage, sliding in a
channel cut into the deck, with a small ridge near the open end for the foot to
click over. It fails the one test that matters for a toy: turn the boat over.
The foot needs headroom above it to ride over the ridge, so upside down it
hangs in that headroom, clear of the ridge, and slides straight out. No rigid
shape fixes that -- any path in by sliding is a path out by sliding -- so
something has to spring.

The spring goes in the carriage, not the hull, for two reasons. A broken
carriage is a twenty-minute reprint and a broken deck is a day. And a carriage
prints small, so its spring can be laid out to bend **in the plane of the bed**:
the strain then runs along the extruded lines rather than across the layers,
which is where PLA is weakest.

### The slide and the clamps

[`cannon/slide.py`](cannon/slide.py) holds the interface, in printed
millimetres like `TrunnionSpec`, and both sides are cut from it. The deck gets a
**slide**, a low rail whose **head** is wider than its **neck**, so it has a lip
down each side, and a **chock** across each end. The lip's underside is at 45
degrees, so the rail prints with the hull.

The carriage's bed is raised over a tunnel the slide runs through, with a gable
roof at 45 degrees rather than a flat span. In the tunnel are two **clamps**:
arms running the carriage's full length, fixed to the brackets at their middles,
each with a hooked **jaw** at both ends. Press the carriage down onto the slide
and the jaws ride down the head's chamfered top edges, spread, and snap under
the lip. Clipped on, the carriage cannot lift off whichever way up the boat is,
and it can only slide as far as the chocks, which stop it run out at one end and
recoiled at the other. The jaws span the whole carriage, so the chocks sit just
clear of its ends.

A jaw is the rail's profile grown by the fit, and the one number to remember is
that growing a 45-degree face by `fit` square to itself leaves `fit * sqrt 2` of
room *vertically*. That is the carriage's play upward, and a test pins it.

Each clamp arm is 13.5mm long and bends 0.45mm clipping on: 0.37% strain, well
inside the 2% PLA takes. `Slide.strain` does the sum and a test holds it under
1%.

### Height comes from what the gun has to clear

`CarriageSpec.axis_height` is the trunnion axis above the deck, taken from the
scan: 13.9mm above the forecastle for the bow gun, and for the 9-pounders
whatever puts the axis 15.6mm above the platform where the barrel crosses the
rail. Everything else follows. The bed is as high as it can be while the base
ring clears it at the quoin's elevation (`breech_drop`); the bracket steps hang
off the rail's top; the quoin is sized to catch the breech at `elevation`, and
ends short of the base ring.

That last one was a fixed number until the 9-pounder showed why it cannot be.
A shorter barrel puts its base ring over the old quoin, so the breech sat on the
ring and the gun was a hair into the wedge. A test asks the physical question
-- the gun at its elevation is clear of the carriage, half a degree more and it
is in the quoin -- and `quoin_to` is now derived from where the ring starts.

The gun rests on the quoin because it is breech-heavy, by a third of a
millimetre. That is worth a test too: the other way round it would tip
muzzle-down onto the rail.

### Running out as far as the hull allows

`mount` solves each gun against the lines. A broadside gun runs out until its
carriage stands `CLEARANCE` off the planking, measured **at the deck**, since
the side flares and is narrowest there, or until its outer chock would come
within `SKIN` of the outside, whichever is nearer. The bow gun's run-out is the
scan's -- its muzzle ends up 0.5mm past the stem, against the scan's 0.7 -- and
is only checked.

Then `Mount.clearance` walks the whole recoil and asks how far the barrel's
underside stands over the rail. It has to be the whole run, not just the ends:
recoiling draws thicker, lower barrel over the rail for as long as the muzzle is
still outboard of it. The barrel's radius comes from `cannon.outline`, a
deliberately generous envelope, with the swell's radius all the way back to the
neck and every ring at full height. `mounts` refuses any gun under `MARGIN`. At
the scan's heights the bow gun clears by 0.50mm and the broadside guns by 0.52
and 0.44, which is why the real boat needed no gunports.

Those were a millimetre apiece until the barrels were measured off the scan
rather than proportioned from a founder's table: the true piece is half a
calibre fatter at the breech, and the fat end is what passes over the rail. The
tightest point is the rail's inboard edge with the gun run out, and 0.44mm is
about an inch at full size -- which is roughly what the scan itself shows under
the starboard 9-pounder. There is no slack left to spend on a thicker rail.

`fit_guns` lays the slides after `build`, like every other fitting, and then
probes the fitted hull: deck under each corner of the carriage and open air
above it, at both ends of its run.

### Two build123d surprises

**`location * compound` moves the compound, not its children.** The first
assembled boat reported every gun two cubic centimetres into the hull, because
the children were still sitting at the origin -- in the bow's solid plug.
`guns.placed` moves each piece.

**Mirroring a profile reverses its winding, and `extrude` follows the face's
normal.** The port clamp's jaw extruded backwards, off the end of the carriage,
as a second solid. `Slide.jaw_profile` returns its corners anticlockwise on
either side.

### The first gun came off the bed in pieces that would not go together

The gun was held by two separate trunnion pegs, each pressed 1.2mm into a blind
socket in the barrel, with a small grooved **cap square** sliding aft over each
one along a hooked rail. Printed, it failed twice over. The pegs fell straight
back out of the barrel while the gun was being offered up to the carriage -- 1.2mm
of printed hole grips nothing, and there was no way to hold the peg in while
lining the other one up. And the cap squares, 6.1 x 2.5 x 1.6mm, were too small
for their own geometry: a 0.55mm wall grooved to catch a 0.5mm hook leaves
nothing that survives a nozzle.

Both go away if the trunnion is **one pin bored right through the piece**. It
cannot fall out of a hole it passes through, it needs no press fit to stay put,
and it turns both jobs -- locating the gun and pivoting it -- into one part that
is among the easiest in the box to print. What is left is holding the pin down.

### Sprung lips went soft in an afternoon

The first answer was a **clip**: a bed with a detent over it and the two lips
either side cut free of the bracket by a slot apiece, so that what gave was a
beam of known length rather than the whole bracket. The arithmetic was fine --
0.7mm thick on a 3.9mm arm, strained 0.8% by the pin going past, against the 2%
PLA yields at -- and it was wrong anyway. PLA creeps. A lip bends across the
printed layers, which is the direction it creeps in fastest, and every clip-in
leaves a few microns of set. A couple of hours of a child's play is some
hundreds of cycles, and the 0.12mm each lip had to give with was gone.

The lesson is not that the numbers were wrong but that they were the wrong
numbers. Yield strain says whether a spring survives being bent once. Nothing in
that calculation says what happens when it is bent a thousand times, and at this
scale there is no travel to spare for creep to eat.

### A bayonet has nothing to creep

So the pin stopped being round. Two flats are milled down its length -- 2.6mm
across the round, 1.7mm across the flats -- and each bracket's slot is 1.85mm
wide. The pin passes at one angle of the gun and is held by solid bracket at
every other, and the hole through the barrel carries the same flat, so turning
the gun turns the pin. Where the gun rests, 20 degrees from lined up, its
corners stand 0.42mm under the lips. `TrunnionSpec.release` holds the angle they
line up at, and both the gun's hole and the brackets' slots are cut from it, so
they cannot disagree.

Two traps, both now asserted. The lips' undersides have to meet the bed *above*
its widest point: run the 45-degree line from the slot wall to the widest point
and it passes 1.03mm from the axis, inside the 1.3mm the pin needs, so the pin
drops in and jams instead of turning. And the flats cannot be cut too deep --
lying on a flat to print, the arcs undercut the bed by `asin(waist/shank)`, so
the pin is only self-supporting while the waist is no wider than `shank/sqrt 2`.

Printing it on a flat is the other dividend. Standing on end it had 3.5mm2 of
first layer under an 11.7mm tower, and its layers ran across the way it is
loaded; on its side it has a real contact patch and the layers run along it.

## Part 13: the joinery

[`details.py`](details.py) adds the timbers that make the model read as the
boat in the scan: knees on the middle platform, benches down both sides of the
quarterdeck, the keelson along each well and the stem on the bow. The seams
between the deck planks are cut in [`hull.py`](hull.py). Every size comes off
the scan, and `designs/measure_scan.py` prints the numbers again.

### Merged, and reaching into what they stand on

Each piece is a union with the hull, so it prints as part of it. A union that
only *touches* the hull is the thing to avoid: coincident faces make fragile
booleans, and a piece that stops a hair short leaves a crack that the slicer
reads as two parts. So every piece reaches `OVERLAP` (0.3mm) into the planking
and is sunk `SINK` into the deck, both well under the 2mm wall.

The side flares, which is why nothing here is a box against it. A knee's back,
a bench's back and a beam's ends all follow `hull.inner_half_width` up from the
deck, the same line the cavity was cut to. A box standing square to the deck
would reach the planking at its foot and stand 0.4mm clear of it at the top of
a 2mm beam.

All the pieces are fused in one call, `hull.fuse(*pieces)`, rather than one at a
time. Each boolean against the hull costs about the same whatever the size of
the piece, so seventeen of them cost 10s where one costs 4s. The end knees overlap
their beams, which is why each piece is passed as its own tool: a single
compound of overlapping solids is not a valid argument.

### Knees and their beams

The scan has five knees a side on the middle platform. A pair stands at each
end, on a cross-beam that is also the platform's edge. Pairs stand at 0.43 and
0.544, and there is one knee on each side opposite a gun, where the gun's own
side has none because that is where it runs out. `HullSpec.knees` holds only the
ones between the ends. The end pairs and their beams are placed from the
deck's edges, the way the mast step is placed from the wells, so moving the
platform moves them with it.

The knee's profile is drawn in the transverse plane and extruded 1.6mm along
the boat. Its back follows the inside face up to half a millimetre under the
rail. Its tall arm tapers from 2.3mm to 1.6mm, then there is a 5mm curve into
the low arm, which runs 15.6mm across the deck and slopes down to it at the end.
Every face is vertical or faces up, so it prints with the hull without
supports.

### Benches, and the awning standing on them

The benches run from the quarterdeck's forward edge to 0.868, 6.2mm high and
8.8mm deep. They are solid to the deck, because the scan's front boards run all
the way down. They cover where the aft pairs of awning legs stood, so those legs
now stand on the benches: `awning.frame` asks `details.bench_top` what is under
each leg and uses the seat when there is one. The roof is planar, so the
uprights just get shorter. That is also why `fit_details` runs before
`fit_awning`, since the sockets are bored into the seats.

The forward legs moved too, from 0.42 and 0.55 to 0.412 and 0.57: each would
have stood on a knee.

### The keelson and the stem

The keelson is a 4mm bar standing 1.8mm proud of each well's floor. It runs
into the bulkhead at each end, and the mast's tube and bore go straight through
it.

The model's bow is a plumb flat face about 3.7mm wide, where the real one is a
raked V. So the stem is a separate wedge on that face, and follows the scan's
curve rather than the model's:

```python
proud = STEM_PROUD - aft  # the planking meets the stem 220mm aft of its face
```

It stands 4mm proud at the rail and rakes back as it goes down, until it has
faded into the bow about 9mm up. It never reaches the bed, so the bottom stays
flat. The bow gun's clearance check counts the stem's head as part of the rail
it fires over.

The lines plan's own bow already carries a stand-in for the stem: the faired
sheer runs on in a straight line to a 205mm-wide face, 134mm forward of where
its curve ends. The stem stands in front of that, so the hull is 304mm overall
rather than 300. Taking the stand-in out of the drawing and letting the stem
replace it was tried. It made a stem narrower than the bow it stood on, which
looked worse than the extra length.

### Plank seams

The planks all run fore and aft, as the scan shows, so the seams are straight
grooves 0.5mm wide and 0.2mm deep. A plank is centred on the centreline, and the
width is set per deck: `Deck.plank` is 7.8, 8.0 and 5.9mm from bow to stern. The
depth is capped under 0.3mm for a reason: `fit_guns` probes 0.3mm below the deck
under each carriage's corners, and a seam there must not read as a hole.

`_seams` does not intersect a comb with the cavity. It solves each groove's
length instead, running it only where the deck is wide enough to leave `margin`
before the side. That is the same shape at a quarter of the cost. A groove runs
out past a platform's open edge rather than ending on the face of its bulkhead.
All three decks' grooves are cut in one boolean.

Anything standing across the seams is where this gets fragile. A knee's
footprint cut nearly across the strip of deck between two grooves, leaving a
neck 0.3mm wide. OCCT's mesher dropped the whole strip, and the export had a
hole in the deck. Later an awning boss did the same with an edge 0.01mm from a
seam. So `hull.clear_of_seams` says how far to move anything standing on a deck
to keep its edges `Seams.clearance` (1mm) from any seam. The knees move their
ends by it, and the awning moves its bosses. A test exports the fitted hull, so
the next such sliver fails the suite rather than the slicer.

That was not the whole story. With the aft boss clear of every seam, the export
still dropped a strip of quarterdeck. The fault was the mesher's settings:
build123d's `tessellate` treats its tolerance as *relative* to each edge's
size, and meshed that way, the quarterdeck's comb-shaped top face lost a strip.
[`export.triangulate`](export.py) meshes first with the tolerance absolute,
which is also the only way `MESH_TOLERANCE` actually means 0.05mm. Both fixes
are needed: with the clearance off, a neck 0.01mm wide will not mesh at any
setting.

## Making your own hull

If you want to do this for a different boat:

1. **Draw four curves** in DXF over your reference — sheer and chine, each in
   half-breadth and profile. Keep them single-valued in X. Put the ends'
   closing lines on their own layer or omit them.
2. **Point [`lines.py`](lines.py) at your layer names** and set `PROFILE_OFFSET`
   to however far apart you drew the two views.
3. **Set the spec** in [`main.py`](main.py): `length`, `wall`, `decks`,
   `bulge`, and any joinery -- `knees`, `benches`, `keelson`, `stem`, and a
   plank width per deck with `seams`.
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
| [`rig.py`](rig.py) | mast, yards, sails, and the socket in the hull |
| [`awning.py`](awning.py) | the awning frame, its canvas, and its sockets in the decks |
| [`details.py`](details.py) | knees, benches, keelson and stem, merged into the hull |
| [`guns.py`](guns.py) | where each gun stands, how far it runs out, and its slide in the deck |
| [`cannon/`](cannon) | the barrel, carriage, trunnion pin, slide and its proof piece |
| [`assembly.py`](assembly.py) | the parts put together, for looking at |
| [`tests/`](tests) | geometry assertions |
| [`PRINTING.md`](PRINTING.md) | slicer settings, flotation, ballast |

Line links point at the current commit and will drift; the function names are
the durable part.
