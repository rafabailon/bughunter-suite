.PHONY: test api e2e report coverage run

test:
	python -m pytest

api:
	python -m pytest -m api

e2e:
	python -m playwright install chromium
	python -m pytest -m e2e

report:
	python -m pytest --html=reports/pytest-report.html --self-contained-html

coverage:
	python -m pytest --cov=src --cov-report=term-missing --cov-report=html:reports/coverage

run:
	python -m app
