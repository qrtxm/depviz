CONFIG ?= examples/config.toml
ARGS ?=

.PHONY: run test

run:
	PYTHONPATH=src python3 -m depviz $(CONFIG) $(ARGS)

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -t . -v
