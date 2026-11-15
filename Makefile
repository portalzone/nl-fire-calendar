# Short commands for this project. Run "make help" to see them.
# If "python" is not found on your computer, use: make test PY=python3
PY ?= python

help:
	@echo "make install     install the Python packages (and the test browser)"
	@echo "make data        rebuild the fire data from data/raw (needs the FIRMS downloads)"
	@echo "make co          rebuild the carbon monoxide table from data/raw/csa"
	@echo "make test        run all tests (pipeline and browser)"
	@echo "make test-fast   run only the pipeline tests"
	@echo "make coverage    run the pipeline tests and show how much code they cover"
	@echo "make serve       open the app at http://localhost:8000"

install:
	$(PY) -m pip install -r requirements-dev.txt
	$(PY) -m playwright install chromium

data:
	$(PY) pipeline/build_harmonized.py

co:
	$(PY) pipeline/build_co.py

test:
	$(PY) -m pytest

test-fast:
	$(PY) -m pytest --ignore=tests/e2e

coverage:
	$(PY) -m pytest --ignore=tests/e2e --cov=pipeline --cov-report=term-missing

serve:
	cd app && $(PY) -m http.server 8000

.PHONY: help install data co test test-fast coverage serve
