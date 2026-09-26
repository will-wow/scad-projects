# The Smithsonian's scan

`../measure_scan.py` reads two meshes from here, which are not in git:

- `p0-Deck-89k-512.glb` -- the deck, guns, mast stump and fittings
- `p1-Hull-83k-512.glb` -- the hull

They are the Smithsonian's 3D scan of the gunboat *Philadelphia*, in the
National Museum of American History, downloaded from the Smithsonian 3D
Digitization site (3d.si.edu) at the 512 texture size. Save them here under
exactly those names.

They stay out of the repository because the Smithsonian's terms allow download
for non-commercial, educational and personal use but are not an open licence,
so committing them would be redistributing them -- and at 2MB each they would
sit in the history for good.

The model never reads them. They are only for checking the lines, the decks
and the guns against the real boat.
