#!/bin/bash
# Docker startup script for Yak Similarity Analyzer

set -e

echo "======================================================"
echo "🐂 Yak Similarity Analyzer Docker Setup"
echo "======================================================"

# Create necessary directories if they don't exist
mkdir -p data uploads results license_data dual_keys

# Check if running in Docker
if [ -f /.dockerenv ]; then
    echo "Running in Docker environment"
else
    echo "Running in host environment"
fi

echo "------------------------------------------------------"
echo "📋 Quick Start Instructions:"
echo ""
echo "1. Build and run with Docker Compose:"
echo "   docker-compose up --build"
echo ""
echo "2. Or run with Docker directly:"
echo "   docker build -t yak-analyzer ."
echo "   docker run -p 5000:5000 -v \$(pwd)/data:/app/data yak-analyzer"
echo ""
echo "3. Access the web interface:"
echo "   http://localhost:5000"
echo ""
echo "4. For first-time setup:"
echo "   docker exec -it <container-name> python tools/client_key_generator.py"
echo ""
echo "5. To generate authorization:"
echo "   docker exec -it <container-name> python tools/provider_key_generator.py client_key.json"
echo "------------------------------------------------------"

# If running directly, start the application
if [ "$1" = "run" ]; then
    echo "Starting Yak Similarity Analyzer..."
    python run.py
else
    echo "Use 'docker-start.sh run' to start the application"
fi