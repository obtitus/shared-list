.PHONY: test lint
test:
	uv run test_api.py

# stop the build if there are Python syntax errors or undefined names
# exit-zero treats all errors as warnings. The GitHub editor is 127 chars wide
lint:
	uv run flake8 . --exclude ".venv" --count --select=E9,F63,F7,F82 --show-source --statistics
	uv run flake8 . --exclude ".venv" --count --exit-zero --max-complexity=15 --max-line-length=127 --statistics
