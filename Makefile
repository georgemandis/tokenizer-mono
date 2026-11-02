PY := .venv/bin/python
RECIPES := $(filter-out tokenizer,$(notdir $(wildcard fonts/*)))

.PHONY: all setup fetch clean test $(RECIPES)

all: $(RECIPES) tokenizer

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

shot: smoke
	$(PY) tools/shot.py build/smoke/SmokeMono-Regular.woff2 build/smoke/shot.png "fire fired misfire fire." "Fire! campfire, fire, FIRE"

# make tokenizer            builds every tokenizer variant
# make tokenizer V=o200k    builds one
tokenizer:
	$(PY) tools/build.py fonts/tokenizer $(if $(V),--variant $(V))

tokcheck:
	$(PY) tools/tokcheck.py $(or $(V),all) fonts/tokenizer/corpus-large.txt
