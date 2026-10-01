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
stale bytecode and repaint the _old_ geometry.

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

The DXF is drawn transom-first, with X increasing toward the bow; `lines.py`
mirrors it on load, so everywhere in the model X is the distance aft of the
bow.

The faired bottom is flat -- one height, no rocker to interpolate, and the toy
sits flat on a printer bed. `FAIR_BASE_PROFILE` starts where the flat does; forward
of that the bottom sweeps up round a quarter-ellipse to where the sheer ends,
leaving a flat face as wide as the lines are there. The stem is one board bent
round that face, `lines.STEM_DEPTH` thick, its foot flat on the bed and its head
at the rail. The lines are the planking's only; the stem is not drawn.

`details.py` merges the boat's joinery into the hull, all sized from the scan:
the knees and cross-beams on the middle platform, benches down both sides of
the quarterdeck, and the keelson along each well. The decks get shallow seams
between fore-and-aft planks.

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

The planks on the decks are grooves rather than geometry: `Seams` gives the one
width and depth, a `Deck` its plank width, and `_seams` solves each groove's
length against the inside of the hull instead of intersecting a comb with the
cavity -- the same shape at a quarter of the cost. The floors of the open wells
are grooved the same way, from `Well`; there the innermost seam is placed rather
than centred, since the keelson runs down the middle of every well and the
mast's tube stands in the forward one.

The grooves are 0.2mm deep, which is shallow for a reason: `fit_guns` probes
0.3mm under each corner of a carriage for deck, and a seam there must not read
as a hole. `clear_of_seams` is the other half of that -- anything standing on a
planked deck is moved until none of its edges is within a millimetre of a seam,
because a strip thinner than that gets dropped by the mesher and the export ends
up with a hole in the deck.

## The guns

`cannon/cannon.py` turns the barrel as one solid of revolution: a half-profile
sketched on `Plane.XZ` and revolved round Z, with the bore subtracted after.
The parts carry their period names -- swell of the muzzle, neck, muzzle
astragal, reinforce rings, base ring, base of the breech and cascabel -- and
the proportions are in calibres, the way the gunfounders wrote them, so
the 12-pounder in the bow and the 9-pounders on the sides are one `CannonSpec`
at two calibres.

Every one of those proportions is measured off the scan by
[`designs/measure_scan.py`](designs/measure_scan.py), not taken from a founder's
table. The first gun printed thin, and it was: the real piece runs 2.27 calibres
at the neck to 3.70 at the breech over 22.6 calibres of length, where the model
had 2.1 to 2.8 over 20.8. It is the taper that was wrong more than the size --
the muzzle was within a couple of percent, the breech a third too narrow -- and
correcting it put 60% more metal in the barrel.

The rings came off the scan too, later and for the same reason. Laid out by the
founders' rule they sat at 0.14, 0.52 and 0.71 of the length from the muzzle
face, and the trunnions looked off-centre between the after two. On the piece
they come in pairs -- a ring with its astragal -- at 0.45/0.51 and 0.625/0.675,
with the muzzle astragal at 0.14 and one more over the vent at 0.91; and the
trunnion axis at 0.57 falls within a quarter of a percent of halfway between
the two that flank it. The heights are the scan's scaled together, since
detrended they read 6 to 11mm proud, which at 1:55 would round off to nothing.

```sh
just watch cannon/cannon.py     # preview the gun on its own
just test tests/test_cannon.py
```

It is built in print orientation: muzzle face down on the bed, bore up. Every
ring is a half-round with its underside cut off as a chamfer at `max_overhang`,
and the bore ends in a point at the same angle, so the gun prints standing on
its muzzle with a brim and no support. The bore only goes a few calibres in, so
the trunnion bar bears on solid metal.

The cascabel is the one place the toy departs from the piece. A real gun carries
a ball on a slender neck, which is what this drew first -- and at 1:55 that is a
1.5mm neck holding a 2.9mm knob, one printed layer interface carrying a lever two
millimetres long. It snapped off in play. It is now a plain stub with a dome on
its end, 1.2 calibres through: the same reach aft, a fifth of a millimetre
narrower, and five times the section in bending. The dome is also the only round
on the piece that faces away from the bed, so it needs no chamfer under it.

### Carriage and trunnions

Three printed parts per gun: the barrel, one **trunnion** bar, and a
**carriage** -- two **brackets** on a **bed**, with a **quoin**, the wedge a real
gun's breech rests on.

The bar goes right through the piece and into both brackets, and it is square:
2.4mm across the flats. Every hole it goes through is a **diamond**, the square
stood on a corner, so the gun is fixed on it at the carriage's elevation and
cannot turn. It is a press fit in the brackets, so the gun is captive as well:
there is no way out of a hole the bar passes through. To take it apart, push the
bar back out with a needle.

The press is the printer's rather than the drawing's. All three holes are drawn
a few hundredths _over_ the bar and come out under -- a printed hole shrinks --
with the brackets' the tightest of them. Drawn nominal they were tight enough
that the bar wanted a vice.

That is the fifth scheme, and each of the four before it failed on the print bed.
Separate pegs pressed into blind sockets, with a sliding cap square over each,
fell apart in the hand: 1.2mm of printed hole is not a press fit, and a 2.5mm cap
square has no room for a groove and a hook. Sprung lips either side of a slot
held the gun for an afternoon of play and went soft -- 0.7mm of PLA bending
across its printed layers creeps a few microns each time. A bayonet -- a pin with
two flats, passing a slot at one elevation -- let the gun wobble sideways out of
the slot, because a slot the pin can get into at one angle is a slot it can work
along at every angle. And a round pin pressed into round holes held the gun on
and let it fall forward: the printed gun is heavier at the muzzle than the model
says, because at sparse infill the thin chase prints as nearly solid wall and the
fat breech as mostly air. The round holes sagged, too, so the pin went in tight.

A diamond answers both. It holds the angle, and its four faces each lean 45
degrees, which is the one shape a horizontal hole can have with nothing round to
sag.

Two things are easy to get wrong here, and both are asserted. The angle the bar
holds is the carriage's `elevation`, not level: level, each barrel would stand
0.6 to 0.7mm into the rail it fires over. So the brackets' diamond is turned four
degrees from the gun's, which would lean one roof face 49 degrees, and `diamond`
swings that face back up to 45. That leaves a sliver of clearance over one upper
face of the bar, 0.17mm at its widest, on the side the gun's weight never bears
on. And the bracket left over the diamond's apex is the one ligament a press fit
could split, so `cheek` -- how far the bracket stands over the axis -- is set
from that: 3.0mm, leaving 1.18.

`cannon/trunnion.py` holds the fits, and the barrel and the carriage both cut
their own geometry from that one `TrunnionSpec`. Its numbers are in printed
millimetres rather than calibres: a clearance does not scale. The brackets' holes
are drawn **nominal**, exactly the bar, because a printed hole comes out a tenth
or two under size already and that undersize is the grip; if a print will not
take the bar, `press` goes negative. The barrel's hole is drawn 0.05 over, since
it is the longest of the three and the bar has to slide through it -- but any of
that which survives printing lets the muzzle droop, about 1.2 degrees per 0.05,
and the barrel clears its rail by only a third of a millimetre a degree.

The bar prints lying on a face, with its long edges relieved a quarter of a
millimetre: a diamond's corners print a little filled, and a sharp corner would
jam in them before the faces met.

```sh
just watch cannon/assembly.py   # the three parts together
just watch cannon/carriage.py
just build                      # all of them, with the hull and the rig
```

### In the boat

Each gun runs on a **slide** printed into its deck, a rail with a lip down each
side and a **chock** across each end (`cannon/slide.py`). The carriage clips
onto it from above: two springy **clamps** in a tunnel under its bed snap their
jaws under the lip. Clipped on, it cannot come off whichever way up the boat
is, and it runs between the chocks: out until the muzzle is over the side, and
back in recoil -- 8mm for the 9-pounders, and for the 12-pounder nearly the
whole forecastle, as the kit's does. Pull it straight up, firmly, to take it off.

Before printing a hull to find out whether the carriage runs, print the rail on
its own: `cannon/proof.py` is a 46 x 17 x 4.6mm patch of deck with the slide sunk
into it, chocks and all, off the bed in a few minutes.

```sh
just build --model cannon.proof:model=proof-12 --model cannon.proof:nine=proof-9
```

The rail is the same for both guns -- the carriages are the same length and clip
to the same `Slide`, and the pads keep the short 8mm run -- so the two pieces
differ only in how wide the deck around it is. The 12-pounder's is the wider and takes either
carriage; a test asserts the rail on the pad is the rail the hull gets, since
otherwise the print proves nothing.

`guns.py` places them from the scan -- the 12-pounder on the forecastle firing
over the stem, a 9-pounder each side of the middle platform -- runs each out as
far as the hull allows, and checks the barrel clears the rail over its whole
run. At the scan's heights none needs a gunport, but the bow is notched round
the 12-pounder's barrel, the stem stopping just under the sheer, as on the boat. HOW-IT-WORKS.md Part
12 has the reasoning.

To arm the boat, print:

| Part | File | Count |
| --- | --- | --- |
| 12-pounder barrel | `philadelphia-gun.3mf` | 1 |
| 12-pounder carriage | `philadelphia-carriage.3mf` | 1 |
| 9-pounder barrel | `philadelphia-gun-9.3mf` | 2 |
| 9-pounder carriage | `philadelphia-carriage-9.3mf` | 2 |
| trunnion bar | `philadelphia-trunnion.3mf` | 3 |

Put the carriage on its slide first. Then stand the barrel between the brackets,
line its diamond up with theirs, and press the bar through until it is flush on
both sides. It is not meant to come apart again -- push the bar back out with a
needle if it must.

`cannon/assembly.py` is not printed. It hangs the gun off a `RevoluteJoint` on
the trunnion axis -- positive `elevation` raises the muzzle -- and the tests
assert that no two parts there share any volume, which is the only way to catch
a fit that is a tenth of a millimetre too tight.
