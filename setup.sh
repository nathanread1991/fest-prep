#!/bin/bash

# Festival Playlist Generator - Setup Script Launcher
# This script launches the Python setup script with proper error handling

set -e  # Exit on any error

echo "🎵 Festival Playlist Generator - Setup Launcher 🎵"
echo

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is required but not found."
    echo "Please install Python 3 and try again."
    exit 1
fi

# Check Python version (require 3.8+)
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
required_version="3.8"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo "❌ Error: Python 3.8 or higher is required."
    echo "Current version: Python $python_version"
    echo "Please upgrade Python and try again."
    exit 1
fi

echo "✅ Python $python_version detected"
echo

# Check for command line arguments
if [ "$1" = "--change-admin-password" ] || [ "$1" = "-p" ]; then
    echo "🔐 Launching admin password change utility..."
    echo
    python3 change_admin_password.py
    exit 0
fi

# Run the setup script
echo "🚀 Starting interactive setup..."
echo
python3 setup.py

echo
echo "✨ Setup script completed!"
echo
echo "💡 Tip: To change admin password later, run:"
echo "   ./setup.sh --change-admin-password"
echo "   or: python3 change_admin_password.py"