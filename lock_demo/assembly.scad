include <base.scad>

// Assembly of all parts for development.

color("gold") Plug();
color("yellow") Cap();
color("orange") CapPin();
color("orange") PlugPinBar();
color("teal") RetainingPin();
color("aqua") RetainingSpring();
color("green") Shell();
color("blue") DriverPins();
color("red") KeyPins();
up(show_on_key ? 0 : -key_l - 5) color("gray") Key();
//up(show_on_key ? 0 : -key_l - 5) color("gray") BadKey();
