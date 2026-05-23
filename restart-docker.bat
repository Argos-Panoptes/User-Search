@echo off
REM Script to restart Docker services for the signal-analyzer

cd /d "%~dp0"

echo Stopping and deleting containers and volumes...
docker compose -f docker-compose-dev.yml down -v

echo Starting containers...
docker compose -f docker-compose-dev.yml up -d

echo Done!
