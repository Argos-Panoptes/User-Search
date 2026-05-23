#!/bin/bash
# Script to restart Docker services for the signal-analyzer

# Ensure we are in the directory containing the docker-compose file
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "Stopping and deleting containers and volumes..."
docker compose -f docker-compose-dev.yml down -v

echo "Starting containers..."
docker compose -f docker-compose-dev.yml up -d

echo "Done!"