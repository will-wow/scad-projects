# Put build artifacts in ./dist (easy to gitignore)
SHELL := /usr/bin/sh

SCAD := base.scad

# Match module lines and turn them into dist/<Module>.3mf targets
# (Note: $$ is required so a literal $ reaches sed from within a Makefile.)
TARGETS := $(shell sed '/^module [A-Z][a-zA-Z0-9]*().*$$/!d;s/^module //;s/().*/.3mf/;s|^|dist/|' $(SCAD))

all: dist $(TARGETS)

dist:
	mkdir -p dist

# auto-generated .scad files with .deps make make re-build always. keeping the
# scad files solves this problem.
.SECONDARY: $(TARGETS:.3mf=.scad)

# explicit wildcard expansion suppresses errors when no files are found
include $(wildcard dist/*.deps)

dist/%.scad: | dist
	echo -ne 'include <../$(SCAD)>\n$*();' > $@

dist/%.3mf: dist/%.scad | dist
	openscad -m make -o $@ -d $@.deps $<
