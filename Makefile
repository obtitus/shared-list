.PHONY: run test lint docker-build docker-run docker-up docker-down docker-logs docker-clean test-playwright icons deploy

run:
	uv run app/main.py

# Python testing and linting
test:
	$(MAKE) docker-down
	-pkill -f app/main.py
	uv run python -m unittest discover tests --failfast 2>&1 | tee unittest.log
	$(MAKE) test-playwright
	@echo "=== Unittest Summary ==="
	@grep -A 2 "^Ran " unittest.log || echo "Could not find unittest summary"



# TypeScript Playwright testing
test-playwright:
	npx playwright test tests/basic-pwa.spec.ts

# stop the build if there are Python syntax errors or undefined names
# exit-zero treats all errors as warnings. The GitHub editor is 127 chars wide
lint:
	uv run flake8 . --exclude ".venv" --count --select=E9,F63,F7,F82 --show-source --statistics
	uv run flake8 . --exclude ".venv" --count --exit-zero --max-complexity=15 --max-line-length=127 --statistics

# Docker commands
# if docker is not running: systemctl --user start docker.service
docker-build:
	docker compose build
	docker buildx history logs

docker-up:
	docker compose up -d

docker-down:
	-docker compose down

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

# Generate PWA icons from source 500x500 icon
icons:
	convert app/static/icons/shopping-cart-500x500.png -resize 16x16 app/static/icons/favicon.ico
	convert app/static/icons/shopping-cart-500x500.png -resize 72x72 app/static/icons/icon-72x72.png
	convert app/static/icons/shopping-cart-500x500.png -resize 96x96 app/static/icons/icon-96x96.png
	convert app/static/icons/shopping-cart-500x500.png -resize 128x128 app/static/icons/icon-128x128.png
	convert app/static/icons/shopping-cart-500x500.png -resize 192x192 app/static/icons/icon-192x192.png
	convert app/static/icons/shopping-cart-500x500.png -resize 256x256 app/static/icons/icon-256x256.png
	convert app/static/icons/shopping-cart-500x500.png -resize 512x512 app/static/icons/icon-512x512.png
	convert app/static/icons/shopping-cart-500x500.png -resize 1024x1024 app/static/icons/icon-1024x1024.png
	convert app/static/icons/shopping-cart-500x500.png -resize 640x1136 app/static/icons/splash-640x1136.png

# Deploy to production server
deploy:
	./deploy.sh
