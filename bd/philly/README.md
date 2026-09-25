# USS Philadelphia (1776)

A 3D-printable model of the Continental gunboat USS Philadelphia, built with
[build123d](https://build123d.readthedocs.io/).

For a tour of how the model is put together -- and how to point it at a
different boat -- see [HOW-IT-WORKS.md](HOW-IT-WORKS.md). For slicer settings,
flotation and ballast, see [PRINTING.md](PRINTING.md).

## Setup

Requires [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).
uv will fetch Python 3.14 itself.

```sh
just sync
```

## The edit loop

In one terminal, start the viewer:

```sh
just viewer
```

That runs the standalone [OCP CAD Viewer](https://github.com/bernhard-42/vscode-ocp-cad-viewer)
at <http://127.0.0.1:3939> — open it in a browser. If you'd rather work inside
VS Code, install the `bernhard-42.vscode-ocp-cad-viewer` extension and open its
**OCP CAD Viewer** panel instead; skip `just viewer` in that case.

In a second terminal, start the watcher:

```sh
just watch              # watches main.py
just watch hull.py      # or any other model file(s)
```

Now every save repaints the viewer in about 0.2s.

The speed comes from not restarting Python: importing build123d takes ~16s cold
and a few seconds warm, so `watch.py` pays that once at startup and then only
re-executes the model file on each change. The camera is left where you put it
(`Camera.KEEP`), and a syntax error or a broken model prints a traceback without
killing the watcher — fix the file, save again, and it picks up where it left off.

The watched file is executed exactly as `python <file>` would run it, so it needs
no special API: its own `if __name__ == "__main__":` block runs and calls
`show`/`show_object`. `just run` executes it the slow way, in a fresh process.

Once the model grows past one file, editing any `.py` under the model's
directory — subpackages included — re-renders too. The project's own modules are
dropped from the import cache each reload, so a change to `parts/hull.py` shows
up immediately rather than serving the copy Python cached on first import. The
watcher also disables bytecode caching for itself: a `.pyc` counts as current
when the source's size and whole-second mtime match, so two quick edits of the
same length (`Box(13, 13, 13)` to `Box(15, 15, 15)`) would otherwise re-import
stale bytecode and repaint the *old* geometry.

Each batch resets the viewer's object stack before re-running, since
`show_object` only ever appends to it — otherwise shrinking a shape would draw
the small one inside the stale large one, and deleting one would do nothing.

## The hull

`lines.py` reads `designs/philadelphia_hull_lines.dxf` — a lines plan derived
from the Smithsonian's scan of the surviving boat, at true 1:1 real-world
millimetres — and `hull.py` lofts it into a hollow solid.

The hull is a hard-chine scow, so every transverse section is a trapezoid:
centreline to chine along the flat bottom, then straight out and up to the rail.
The solid is a loft through those sections, hollowed with OCCT's thick-solid
operation with the deck face removed.

Scale and wall thickness live in `HullSpec` (`main.py` sets them). The source
data is the real 16.4m boat; the default prints it at 300mm, or about 1:55.

All four curves are the hand-faired layers: `FAIR_TOP` and `FAIR_BOTTOM` in the
plan view, `FAIR_SHEER_PROFILE` and `FAIR_BASE_PROFILE` in the profile view.
The raw `SHEER_TOP` / `CHINE_BOTTOM` / `SHEER_PROFILE` / `BASE_PROFILE` entities
are the original scan output, still carrying its artefacts, and are not read.

The faired bottom is flat -- one height from just abaft the forefoot to the
transom, with the stem sweeping up over the first 240mm. No rocker to
interpolate, and the toy sits flat on a printer bed.

## Looking at it headlessly

`just viewer` needs a browser. In a remote or headless session there isn't one,
so `just preview` renders three views to `preview/` as SVG (plus PNG where a
Chromium is available) with a small painter's-algorithm renderer. A hull can be
watertight, correctly scaled and still the wrong shape.

## Recipes

```
just            # list recipes
just sync       # install/refresh the venv from uv.lock
just viewer     # start the browser viewer on port 3939
just watch      # live-reload model files into the viewer
just run        # render once, in a fresh process
just format     # ruff format + fix
just check      # ruff format --check, ruff check, pyright
```

## Exporting and testing

```
just build      # dist/philadelphia.3mf, ready to slice (--stl, --step too)
just test       # the geometry checks
```

3MF rather than STL because it records the unit, so a slicer knows the model is
in millimetres. The export welds the tessellation before writing: OCCT meshes
each face on its own, so a shared edge arrives as two sets of vertices and the
result reads as non-manifold -- which is what makes a slicer offer to repair a
model. It refuses to write a mesh that is still non-manifold after welding.

## The shape of a section

Every transverse section is centreline to chine along the flat bottom, then out
and up to the rail. Straight out and up gives a flat-panelled box; the scan's
topsides visibly swell, so `Bulge` carries the side out of that chord and back.

It is not tumblehome -- nothing on this boat curves back inward -- which is why
one parameter does the job and there is no need to draw station sections and
fair them. `amount` is the height of the swell as a fraction of the side's own
slant height, so it tapers with the hull instead of staying a fixed millimetre
count that would swamp the narrow ends; `peak` is where along the side it is
widest. Both ends are pinned to zero, so the lines plan still decides where the
chine and the rail go.

The swell is applied to the cavity's sections too, at the same height and by the
same distance, so the wall survives without a real polyline offset and without
the self-intersection that offsetting into a curve invites. That only works
because it displaces horizontally: moving points along the surface normal
carries them down the side as well as out, the two swells end up offset in z,
and the cavity leans out through the hull -- which showed up as the subtraction
cutting the boat into three pieces rather than hollowing it.

Every station yields the same number of points, and a test says so. Lofting
between sections whose vertices do not correspond makes OCCT build a common
parameterisation: with counts that varied station to station, the outer loft
alone went from 0.12 seconds to 7.5, and the whole build past eight minutes. It
was still correct, just unusable, which is exactly the kind of failure that
goes unnoticed.

There was a `Planking` alongside this that cut a groove at each plank seam. It
worked, and printed without overhangs, but it was the most intricate code here
by some margin and read busier than the boat wants at 1:55. Removed in favour
of a hull you can hold the whole of in your head; it is in the history if it is
ever wanted back.

## The guns

`cannon/cannon.py` turns the barrel as one solid of revolution: a half-profile
sketched on `Plane.XZ` and revolved round Z, with the bore subtracted after.
The parts carry their period names -- swell of the muzzle, neck, muzzle
astragal, reinforce rings, base ring, base of the breech, cascabel and button
-- and the proportions are in calibres, the way the gunfounders wrote them, so
the 12-pounder in the bow and the 9-pounders on the sides are one `CannonSpec`
at two calibres.

```sh
just watch cannon/cannon.py     # preview the gun on its own
just test tests/test_cannon.py
```

It is built in print orientation: muzzle face down on the bed, bore up. Every
ring and the cascabel's button is a half-round with its underside cut off as a
chamfer at `max_overhang`, and the bore ends in a point at the same angle, so
the gun prints standing on its muzzle with a brim and no support. The bore only
goes a few calibres in, so the trunnion sockets bear on solid metal.

### Carriage and trunnions

Three printed parts per gun: the barrel, two **trunnion** pegs, and a
**carriage** -- two **brackets** on a **bed**, with a **quoin**, the wedge that
holds the breech up. A peg's round shank is a running fit in a socket bored
into the barrel, so the gun elevates on it, and its diamond head keys into a
**trunnion hole** through a bracket. The brackets spread apart to take the gun
and click shut over the heads.

`cannon/trunnion.py` holds the fits, and both the barrel and the carriage cut
their own holes from that one `TrunnionSpec`. Its numbers are in printed
millimetres rather than calibres: a clearance does not scale.

Whether the snap is possible at all comes down to two of them. Bowing a bracket
out by `d` at a hole `h` above the bed strains its surface by about
`3 * bracket * d / (2 * h**2)`, and PLA gives up around 2%; the defaults ask for
1.7%. `bracket` and the pegs' `lead_in` are the numbers to turn if it cracks or
if the gun falls out. The same geometry also goes together by pushing the pegs
in from outside, with no flexing at all.

The horizontal holes are teardrops in the barrel and diamonds in the brackets,
both closing at `max_overhang`, so the roof of each carries itself with the
parts in their printing positions.

```sh
just watch cannon/assembly.py   # the three parts together
just watch cannon/carriage.py
just build --model cannon.carriage:model --name carriage-12pdr
just build --model cannon.trunnion:model --name trunnion-12pdr
```

`cannon/assembly.py` is not printed. It hangs the gun off a `RevoluteJoint` on
the trunnion axis -- positive `elevation` raises the muzzle -- and the tests
assert that no two parts there share any volume.
