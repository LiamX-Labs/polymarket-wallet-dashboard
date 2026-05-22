#!/bin/bash

echo "🚀 Polymarket Wallet Dashboard Setup"
echo "===================================="
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

echo "✓ Node.js version: $(node --version)"
echo ""

# Setup server
echo "📦 Installing server dependencies..."
cd server
npm install
if [ $? -ne 0 ]; then
    echo "❌ Server dependency installation failed"
    exit 1
fi
echo "✓ Server dependencies installed"
echo ""

# Setup client
echo "📦 Installing client dependencies..."
cd ../client
npm install
if [ $? -ne 0 ]; then
    echo "❌ Client dependency installation failed"
    exit 1
fi
echo "✓ Client dependencies installed"
echo ""

# Create .env if it doesn't exist
cd ../server
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Please edit server/.env and set the correct paths:"
    echo "   - TRACKER_DB_PATH: Path to your tracker database"
    echo "   - DASHBOARD_DB_PATH: Path where dashboard database will be created"
else
    echo "✓ .env file already exists"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit server/.env with your database paths"
echo "2. Start the backend:  cd server && npm run dev"
echo "3. Start the frontend: cd client && npm run dev"
echo "4. Open http://localhost:3000 in your browser"
echo ""
