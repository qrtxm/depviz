CONFIG ?= examples/config.toml

.PHONY: run test

run:
	PYTHONPATH=src python3 -m depviz $(CONFIG)

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v
