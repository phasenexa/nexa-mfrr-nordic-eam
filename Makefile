.PHONY: install test lint typecheck format ci clean

install:
	poetry install

test:
	poetry run pytest

lint:
	poetry run ruff check src tests
	poetry run ruff format --check src tests

format:
	poetry run ruff check --fix src tests
	poetry run ruff format src tests

typecheck:
	poetry run mypy src

ci: lint typecheck test

clean:
	rm -rf dist/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/
