#!/bin/bash

# verify_release.sh - Verifies that a Docker image is live on GHCR and functional
# Usage: ./verify_release.sh <version>

set -e

NEW_VERSION="$1"
if [ -z "$NEW_VERSION" ]; then
    echo "Error: Version argument required (e.g., 1.1.8)"
    exit 1
fi

IMAGE="ghcr.io/obtitus/shared-list:v$NEW_VERSION"

# Function to print colored output
print_step() { echo -e "\n\033[1;34m[VERIFY]\033[0m $1"; }
print_success() { echo -e "\033[1;32m[SUCCESS]\033[0m $1"; }
print_error() { echo -e "\033[1;31m[ERROR]\033[0m $1"; }
print_info() { echo -e "\033[1;33m[INFO]\033[0m $1"; }

# 1. Wait for GitHub Action
print_step "Monitoring GitHub Action for tag v$NEW_VERSION..."
if command -v gh &> /dev/null; then
    sleep 10
    while true; do
        STATUS=$(gh run list --workflow "Docker Publish" --limit 1 --json status,conclusion,headBranch -q ".[] | select(.headBranch == \"v$NEW_VERSION\")")
        if [ -z "$STATUS" ]; then
            print_info "Action not found yet... waiting 30s"
            sleep 30
            continue
        fi
        STATE=$(echo "$STATUS" | jq -r '.status')
        CONCLUSION=$(echo "$STATUS" | jq -r '.conclusion')
        
        if [ "$STATE" == "completed" ]; then
            if [ "$CONCLUSION" == "success" ]; then
                print_success "GitHub Action finished successfully."
                break
            else
                print_error "GitHub Action failed with conclusion: $CONCLUSION"
                exit 1
            fi
        fi
        print_info "Action status: $STATE... waiting 30s"
        sleep 30
    done
else
    print_info "gh CLI not found, skipping Action monitoring. Waiting 3 minutes for build..."
    sleep 180
fi

# 2. Verify GHCR image availability
print_step "Verifying GHCR image availability..."
while ! docker manifest inspect "$IMAGE" > /dev/null 2>&1; do
    print_info "Image $IMAGE not found on GHCR yet... waiting 30s"
    sleep 30
done
print_success "Image is live on GHCR!"

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
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/api/version | grep -q '\"version\":\"$NEW_VERSION\"'"]
      interval: 5s
      timeout: 5s
      retries: 10
EOF

# Use subshell to handle directory change safely
(
    cd "$SANDBOX_DIR"
    print_info "Starting sanity container (port-free)..."
    docker compose up -d
    
    print_info "Waiting for version-aware healthcheck..."
    timeout=60
    count=0
    while [ "$(docker inspect --format='{{.State.Health.Status}}' $(docker compose ps -q shared-list-sanity) 2>/dev/null)" != "healthy" ]; do
        if [ $count -ge $timeout ]; then
            print_error "Sanity check failed (timeout or version mismatch)!"
            docker compose logs
            docker compose down
            rm -rf "$SANDBOX_DIR"
            exit 1
        fi
        sleep 2
        count=$((count + 2))
    done
    
    print_success "Verification passed: Image is healthy and reports version $NEW_VERSION."
    docker compose down
)
rm -rf "$SANDBOX_DIR"
