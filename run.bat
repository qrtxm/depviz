@echo off
set CONFIG=%1
if "%CONFIG%"=="" set CONFIG=examples\config.toml
set PYTHONPATH=src
python -m depviz %CONFIG%
