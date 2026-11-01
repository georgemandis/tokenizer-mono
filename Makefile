PY := .venv/bin/python
RECIPES := $(notdir $(wildcard fonts/*))

.PHONY: all setup fetch clean test $(RECIPES)

all: $(RECIPES)

setup:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	./scripts/fetch-plex.sh

fetch:
	./scripts/fetch-plex.sh

$(RECIPES):
	$(PY) tools/build.py fonts/$@

test: smoke
	$(PY) tools/shape.py build/smoke/SmokeMono-Regular.ttf "fire fired misfire fire. Fire"

clean:
	rm -rf build
