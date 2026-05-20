#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Project configuration
PROJECT_DIR="/var/www/project_name"

echo "Deploying updates to $PROJECT_DIR..."

# Navigate to project directory
cd "$PROJECT_DIR"

# Pull latest changes from git
echo "Pulling latest changes..."
git pull

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

pip install -r requirements.txt

# Run database migrations
echo "Running migrations..."
python manage.py migrate

# Restart systemd services
echo "Restarting services..."
sudo systemctl restart slash slash_worker slash_beat

echo "Deployment successful."
