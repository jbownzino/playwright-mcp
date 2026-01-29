#!/bin/bash

# Start the Vite development server for the game
# The game will be available at http://localhost:8080

GAME_DIR="template-youtube-playables"

echo "🎮 Starting game server..."
echo ""

# Check if node_modules exists
if [ ! -d "$GAME_DIR/node_modules" ]; then
    echo "📦 Installing dependencies first..."
    cd "$GAME_DIR"
    npm install
    cd ..
fi

# Start the dev server
echo "🚀 Starting Vite dev server on http://localhost:8080"
echo ""
echo "The game will be available at: http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

cd "$GAME_DIR"
npm run dev
