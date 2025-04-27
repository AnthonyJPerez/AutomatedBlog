#!/bin/bash
# This script copies the necessary deployment templates to the correct location

# Check if script is running in the correct directory
if [ ! -d "deployment-templates" ]; then
  echo "Error: Script must be run from the root directory of the project"
  exit 1
fi

# Make sure deployment-templates directory exists
if [ ! -d "deployment-templates" ]; then
  echo "Error: deployment-templates directory not found"
  exit 1
fi

# Create a copy of pyproject.toml for deployment
cp pyproject.toml deployment-templates/pyproject.toml

# Display success message
echo "Deployment templates copied successfully"
echo "The following files are ready for deployment:"
ls -la deployment-templates/

# Reminder message about GitHub workflow
echo ""
echo "Remember to update your GitHub workflow to copy these files to the root directory during deployment."