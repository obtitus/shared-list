#!/bin/bash

# Deploys to production server with automated pre-deployment steps
# Usage: ./deploy.sh [NEW_VERSION]
# If NEW_VERSION is provided, bumps to specified version
# If no version provided, increments patch version (e.g., 1.1.2 -> 1.1.3)

set -e

# Load environment variables
if [ -f .env ]; then
    source .env
else
    echo "Error: .env file not found, cannot load DEPLOY_HOST, DEPLOY_DIR, DEPLOY_UV."
    exit 1
fi

# Function to print colored output
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

# Function to increment minor version
increment_minor_version() {
    local version="$1"
    local major=$(echo "$version" | cut -d. -f1)
    local minor=$(echo "$version" | cut -d. -f2)
    local patch=$(echo "$version" | cut -d. -f3)
    patch=$((patch + 1))
    echo "${major}.${minor}.${patch}"
}

# Function to cleanup on error
cleanup_on_error() {
    print_error "Deployment failed. Cleaning up..."
    # If we created a new commit but deployment failed, we might want to revert
    # For now, just notify the user
    print_info "If a new commit was created but deployment failed, you may need to manually revert it."
    print_info "Run: git reset --hard HEAD~1 && git push --force origin main"
    exit 1
}

# Set error handler
trap cleanup_on_error ERR

# Parse version argument
NEW_VERSION="$1"
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')

print_step "Starting deployment process..."
print_info "Current version: $CURRENT_VERSION"
if [ -n "$NEW_VERSION" ]; then
    print_info "New version: $NEW_VERSION"
else
    NEW_VERSION=$(increment_minor_version "$CURRENT_VERSION")
    print_info "No version override provided, incrementing minor version to: $NEW_VERSION"
fi

# 1. Check git status is clean
print_step "Checking git status..."
if ! git diff-index --quiet HEAD --; then
    print_error "Working directory is not clean. Please commit or stash changes before deploying."
    print_info "Run: git status to see untracked files"
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    print_error "There are untracked files. Please commit or stash them before deploying."
    print_info "Run: git status to see untracked files"
    exit 1
fi

print_success "Git status is clean"

# 2. Check if this is a rollback (tag already exists)
print_step "Checking if tag v$NEW_VERSION exists..."
if git rev-parse "v$NEW_VERSION" >/dev/null 2>&1; then
    print_info "Tag v$NEW_VERSION exists - performing rollback"
    print_info "Skipping tests and version bump, proceeding to deployment"
    VERSION_EXISTS=true
else
    print_info "Creating new version v$NEW_VERSION"
    VERSION_EXISTS=false

    # 3. Run make lint test to ensure all tests pass
    print_step "Running tests and linting..."
    print_info "Press any key within 5 seconds to skip tests (for debugging/quick revert)..."
    if read -t 5 -n 1; then
        print_info "Tests skipped by user"
    else
        if ! make lint test; then
            print_error "Tests or linting failed. Please fix issues before deploying."
            exit 1
        fi
        print_success "All tests and linting passed"
    fi

    # 4. Handle version bumping
    print_step "Bumping version from $CURRENT_VERSION to $NEW_VERSION"

    # Update pyproject.toml
    sed -i "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml

    # Run uv sync to update uv.lock
    print_step "Updating dependencies..."
    uv sync

    # Commit version changes
    print_step "Committing version changes..."
    git add pyproject.toml uv.lock
    git commit -m "Bump version to $NEW_VERSION"

    # Tag the commit
    print_step "Creating git tag..."
    git tag "v$NEW_VERSION"

    # Push to remote
    print_step "Pushing to remote repository..."
    git push
    git push origin "v$NEW_VERSION"

    print_success "Version bump completed: $NEW_VERSION"
fi

# 6. Verify the public release
./verify_release.sh "$NEW_VERSION"

# 7. Server deployment (tag-based)
print_step "Deploying to production server ($DEPLOY_HOST)..."

ssh "$DEPLOY_HOST" << EOF
    echo "Updating code in $DEPLOY_DIR..."
    cd "$DEPLOY_DIR"
    git fetch origin --tags

    # Deploy specific version tag instead of main branch
    echo "Deploying version tag v$NEW_VERSION..."
    if ! git rev-parse "v$NEW_VERSION" >/dev/null 2>&1; then
        echo "Error: Tag v$NEW_VERSION not found locally"
        exit 1
    fi
    git reset --hard v$NEW_VERSION

    if ! command -v $DEPLOY_UV &> /dev/null; then
        echo "Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
    fi

    echo "Installing dependencies..."
    export UV_CONCURRENT_DOWNLOADS=1
    export UV_CONCURRENT_BUILDS=1
    export UV_CONCURRENT_INSTALLS=1
    $DEPLOY_UV sync --no-dev

    echo "Creating systemd user service..."
    mkdir -p ~/.config/systemd/user
    cat > ~/.config/systemd/user/shared-list.service << EOS
[Unit]
Description=Shared Shopping List PWA
After=network.target

[Service]
Type=simple
WorkingDirectory=$DEPLOY_DIR
ExecStart=%h/.local/bin/uv run app/main.py
Environment=PORT=19099
Environment=HOST=0.0.0.0
Restart=always
RestartSec=5
KillMode=mixed
TimeoutStopSec=10

[Install]
WantedBy=default.target
EOS

    echo "Reloading systemd and restarting service..."
    systemctl --user daemon-reload
    systemctl --user enable shared-list
    systemctl --user restart shared-list
    systemctl --user status shared-list --no-pager

    echo "Waiting for service to be ready on server..."
    timeout=10
    count=0
    while ! curl -f http://localhost:19099/ > /dev/null 2>&1; do
        if [ \$count -ge \$timeout ]; then
            echo "Timeout waiting for service to respond"
            journalctl --user -u shared-list --no-pager --since "5 minutes ago"
            exit 1
        fi
        sleep 1
        count=\$((count + 1))
    done
    echo "Service is ready on server."
EOF

print_step "Waiting for external access..."
timeout=60
count=0
while ! curl -f http://$DEPLOY_HOST:19099/ > /dev/null 2>&1; do
    if [ $count -ge $timeout ]; then
        print_error "Timeout waiting for external access"
        exit 1
    fi
    sleep 1
    count=$((count + 1))
done

print_success "Deployment successful!"
print_success "App available at http://$DEPLOY_HOST:19099"

# Verify deployed version
print_step "Verifying deployed version..."
DEPLOYED_VERSION=$(curl -s http://$DEPLOY_HOST:19099/api/version | jq -r '.version' 2>/dev/null || echo "unknown")
if [ "$DEPLOYED_VERSION" = "unknown" ]; then
    print_error "Failed to retrieve version from deployed application"
    print_info "This might be normal if jq is not installed on the local machine"
    print_info "Please manually verify the version at http://$DEPLOY_HOST:19099/api/version"
else
    if [ "$DEPLOYED_VERSION" != "$NEW_VERSION" ]; then
        print_error "Version mismatch! Expected: $NEW_VERSION, Got: $DEPLOYED_VERSION"
        exit 1
    fi
    print_success "Version verification passed: $DEPLOYED_VERSION"
fi

print_success "New version deployed: $NEW_VERSION"
print_success "Git tag created: v$NEW_VERSION"
