#!/bin/sh
CONFIG="${1:-examples/config.toml}"
PYTHONPATH=src python3 -m depviz "$CONFIG"
