#!/bin/bash

black **/*.py
python3 -m isort .
python3 -m mypy
