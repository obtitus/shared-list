.PHONY: test lint docker-build docker-run docker-up docker-down docker-logs docker-clean

# Python testing and linting
test:
	uv run python -m unittest discover .

# stop the build if there are Python syntax errors or undefined names
# exit-zero treats all errors as warnings. The GitHub editor is 127 chars wide
lint:
	uv run flake8 . --exclude ".venv" --count --select=E9,F63,F7,F82 --show-source --statistics
	uv run flake8 . --exclude ".venv" --count --exit-zero --max-complexity=15 --max-line-length=127 --statistics

# Docker commands
# if docker is not running: systemctl --user start docker.service
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f backend

docker-clean:
	docker compose down
	docker system prune -f
	docker volume prune -f

docker-run:
	docker compose up -d
	@echo "Container started. API available at http://localhost:8000"
	@echo "To view logs: make docker-logs"
	@echo "To stop: make docker-down"

