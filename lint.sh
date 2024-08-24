#!/bin/sh

ruff check  # ruff first, because it's fastest
flake8 .
mypy .
