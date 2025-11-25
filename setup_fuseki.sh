#!/bin/bash
# Setup script for Jena Fuseki Knowledge Base Server
# This script downloads and sets up Jena Fuseki in a separate directory

set -e

FUSEKI_VERSION="4.9.0"
FUSEKI_DIR="apache-jena-fuseki-${FUSEKI_VERSION}"
FUSEKI_URL="https://downloads.apache.org/jena/binaries/apache-jena-fuseki-${FUSEKI_VERSION}.tar.gz"

echo "Setting up Jena Fuseki ${FUSEKI_VERSION}..."

# Check if Java is installed
if ! command -v java &> /dev/null; then
    echo "Error: Java is not installed. Please install Java 11 or later."
    echo "On macOS: brew install openjdk@11"
    echo "On Ubuntu: sudo apt-get install openjdk-11-jdk"
    exit 1
fi

# Check if already downloaded
if [ -d "$FUSEKI_DIR" ]; then
    echo "Jena Fuseki directory already exists: $FUSEKI_DIR"
    echo "Skipping download..."
else
    echo "Downloading Jena Fuseki..."
    wget "$FUSEKI_URL" -O "${FUSEKI_DIR}.tar.gz"
    
    echo "Extracting..."
    tar -xzf "${FUSEKI_DIR}.tar.gz"
    rm "${FUSEKI_DIR}.tar.gz"
fi

echo ""
echo "✓ Jena Fuseki setup complete!"
echo ""
echo "To start the server, run:"
echo "  cd $FUSEKI_DIR"
echo "  ./fuseki-server --port 3030"
echo ""
echo "Or from this directory:"
echo "  cd $FUSEKI_DIR && ./fuseki-server --port 3030"
echo ""
echo "The server will be available at: http://localhost:3030"

