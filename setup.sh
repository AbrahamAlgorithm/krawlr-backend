#!/bin/bash
# Setup script for Krawlr Backend

echo "🚀 Setting up Krawlr Backend..."

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv .venv

# Activate virtual environment
echo "✅ Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "To activate the environment:"
echo "  source .venv/bin/activate"
echo ""
echo "To run the server:"
echo "  uvicorn app.main:app --reload"
echo ""
echo "⚠️  Don't forget to:"
echo "  1. Add your serviceAccount.json file"
echo "  2. Update SECRET_KEY in .env"
echo "  3. In VS Code: Select Python interpreter (.venv/bin/python)"
