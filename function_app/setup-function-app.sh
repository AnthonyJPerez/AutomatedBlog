#!/bin/bash
# Setup script for Azure Functions v2 app
# This script initializes the function app and installs dependencies

echo "Setting up Azure Function App environment..."

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements-functions.txt

# Initialize Function App
echo "Initializing Function App..."
func init --worker-runtime python --model V2

# Install Azure Functions Core Tools if not already installed
if ! command -v func &> /dev/null; then
    echo "Azure Functions Core Tools not found. Please install it following the instructions at:"
    echo "https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local"
    echo "For example, on Ubuntu/Debian:"
    echo "curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg"
    echo "sudo mv microsoft.gpg /etc/apt/trusted.gpg.d/microsoft.gpg"
    echo "sudo sh -c 'echo \"deb [arch=amd64] https://packages.microsoft.com/repos/microsoft-ubuntu-$(lsb_release -cs)-prod $(lsb_release -cs) main\" > /etc/apt/sources.list.d/dotnetdev.list'"
    echo "sudo apt-get update"
    echo "sudo apt-get install azure-functions-core-tools-4"
fi

echo "Setup complete. To start the function app locally, run: func start"