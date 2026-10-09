.PHONY: run test lint format typecheck check clean

run:
	python -m src.roadwatch.web

test:
	python -m pytest tests/roadwatch --confcutdir=tests/roadwatch -q

lint:
	ruff check src/roadwatch tests/roadwatch scripts/roadwatch --extend-exclude src/roadwatch/vendor

format:
	ruff format src/roadwatch tests/roadwatch scripts/roadwatch

typecheck:
	mypy src/

check: lint format test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +

# ---- RoadWatch ----
.PHONY: rw-model rw-run rw-test rw-lint rw-docker

rw-model:
	python scripts/roadwatch/download_model.py

rw-run:
	python -m src.roadwatch.web

rw-test:
	python -m pytest tests/roadwatch --confcutdir=tests/roadwatch -q

rw-lint:
	ruff check src/roadwatch tests/roadwatch scripts/roadwatch

rw-docker:
	docker compose up --build roadwatch
