# CELTM Web Build and Push Script
# This script builds the Docker images and pushes them to the celtm account on Docker Hub.

$DOCKER_USER = "celtm"

Write-Host "--- Starting Build Process ---" -ForegroundColor Cyan

# Build Backend/Worker Image
Write-Host "Building API/Worker image..."
docker build -t $DOCKER_USER/celtm-api:latest ./backend

# Build Frontend Image
Write-Host "Building UI image..."
docker build -t $DOCKER_USER/celtm-ui:latest ./frontend

Write-Host "--- Build Complete ---" -ForegroundColor Green

Write-Host "--- Starting Push Process ---" -ForegroundColor Cyan
Write-Host "Note: Ensure you have run 'docker login' with the '$DOCKER_USER' account."

# Push Images
Write-Host "Pushing API image..."
docker push $DOCKER_USER/celtm-api:latest

Write-Host "Pushing UI image..."
docker push $DOCKER_USER/celtm-ui:latest

Write-Host "--- Push Complete ---" -ForegroundColor Green
Write-Host "IMPORTANT: Please verify that these repositories are set to PRIVATE on Docker Hub." -ForegroundColor Yellow
