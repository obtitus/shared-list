#!/bin/bash

# verify_release.sh - Verifies that a Docker image is live on GHCR and functional
# Usage: ./verify_release.sh <version> [--local]

set -e

NEW_VERSION="$1"
LOCAL_MODE=false
if [ "$2" == "--local" ]; then
    LOCAL_MODE=true
fi

if [ -z "$NEW_VERSION" ]; then
    echo "Error: Version argument required (e.g., 1.1.8)"
    exit 1
fi

IMAGE="ghcr.io/obtitus/shared-list:v$NEW_VERSION"

# Functions to print colored output
print_step() {
    echo -e "\n\033[1;34m[STEP]\033[0m $1"
}

print_success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $1"
}

print_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

print_info() {
    echo -e "\033[1;33m[INFO]\033[0m $1"
}


if [ "$LOCAL_MODE" = true ]; then
    print_info "Running in LOCAL MODE - skipping GitHub and GHCR checks"
    # Always tag local image for the test
    print_info "Tagging local 'shared-list:latest' as '$IMAGE' for local testing..."
    make docker-build
    docker tag shared-list:latest "$IMAGE"
else
    # 1. Wait for GitHub Action
    print_step "Monitoring GitHub Action for tag v$NEW_VERSION..."

    timeout=60
    count=0
    while [[ -z $(gh run list --workflow "Docker Publish" | grep "v$NEW_VERSION") ]]; do
	if [ $count -ge $timeout ]; then
            print_error "Timeout waiting for gh build to show up"
            exit 1
	fi

	sleep 10
	count=$((count + 1))
    done
    print_step "Build triggered, waiting for completed..."

    timeout=60
    count=0
    while [[ -z $(gh run list --workflow "Docker Publish" --branch "v$NEW_VERSION" --json status | grep completed) ]]; do
	if [ $count -ge $timeout ]; then
            print_error "Timeout waiting for gh build completion"
            exit 1
	fi

	sleep 10
	count=$((count + 1))
    done

    if [[ -z $(gh run list --workflow "Docker Publish" --branch v$NEW_VERSION --json conclusion | grep success) ]]; then
	print_error "Build failed:"
	echo $(gh run list --workflow "Docker Publish" --branch v$NEW_VERSION)
	exit 1
    fi
    print_success "Build completed succesfully!"

    # 2. Verify GHCR image availability
    print_step "Waiting for $IMAGE..."
    timeout=60
    count=0
    while ! docker manifest inspect "$IMAGE" > /dev/null 2>&1; do
	if [ $count -ge $timeout ]; then
	    print_error "Timeout waiting for $IMAGE"
            exit 1
	fi

	sleep 10
	count=$((count + 1))
    done

    print_success "Image is live on GHCR!"
fi

# 3. Port-Free Sandbox Sanity Check
print_step "Running version-aware sanity check on GHCR image..."
SANDBOX_DIR=$(mktemp -d)
print_info "Using sandbox directory: $SANDBOX_DIR"

cat > "$SANDBOX_DIR/docker-compose.yml" << EOF
services:
  shared-list-sanity:
    image: $IMAGE
    environment:
      - HOST=0.0.0.0
      - PORT=8000
      - PYTHONPATH=/code
      - UV_NO_DEV=1
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/api/version | grep -q '\"version\":\"$NEW_VERSION\"'"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
EOF

# Use subshell to handle directory change safely
(
    cd "$SANDBOX_DIR"
    print_info "Starting sanity container (port-free)..."
    docker compose up -d

    print_info "Waiting for version-aware healthcheck..."
    timeout=30
    count=0
    while [ "$(docker inspect --format='{{.State.Health.Status}}' $(docker compose ps -q shared-list-sanity) 2>/dev/null)" != "healthy" ]; do
        if [ $count -ge $timeout ]; then
            print_error "Sanity check failed (timeout or version mismatch)!"
            docker compose logs
            docker compose down
            rm -rf "$SANDBOX_DIR"
            exit 1
        fi
        sleep 1
        count=$((count + 1))
    done

    docker compose down
    print_success "Verification passed: Image is healthy and reports version $NEW_VERSION."
)
rm -rf "$SANDBOX_DIR"

# Cleanup local tag if in local mode
if [ "$LOCAL_MODE" = true ]; then
    print_info "Cleaning up temporary local tag $IMAGE..."
    docker rmi "$IMAGE" > /dev/null 2>&1 || true
fi
