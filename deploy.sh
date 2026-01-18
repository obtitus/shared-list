#!/bin/bash

# Deployment script for shared-list PWA
# Deploys to production server

set -e

# Load environment variables
if [ -f .env ]; then
    source .env
else
    echo "Error: .env file not found, cannot load DEPLOY_HOST, DEPLOY_DIR, DEPLOY_UV."
    exit 1
fi


echo "Deploying shared-list to $DEPLOY_HOST..."

ssh "$DEPLOY_HOST" << EOF
    echo "Updating code in $DEPLOY_DIR..."
    cd "$DEPLOY_DIR"
    git fetch origin
    git reset --hard origin/main

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

echo "Waiting for external access..."
timeout=60
count=0
while ! curl -f http://$DEPLOY_HOST:19099/ > /dev/null 2>&1; do
    if [ $count -ge $timeout ]; then
        echo "Timeout waiting for external access"
        exit 1
    fi
    sleep 1
    count=$((count + 1))
done

echo "Deployment successful. App available at http://$DEPLOY_HOST:19099"
