"""Запуск пакета: python -m depviz <config.toml>."""

import sys

from depviz.cli import main

if __name__ == "__main__":
    sys.exit(main())
