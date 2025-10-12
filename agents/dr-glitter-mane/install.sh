#!/bin/bash

# Dr. Glitter Mane Installation Script
# 🦄💉 AI Clinical Maestro Setup

echo ""
echo "==============================================="
echo "🦄💉 Dr. Glitter Mane - AI Clinical Maestro"
echo "==============================================="
echo ""
echo "Welcome! Let's set up your personal medical AI consultant."
echo ""

# Check Node.js installation
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js is not installed."
    echo "Please install Node.js 16+ from https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 16 ]; then
    echo "❌ Error: Node.js version 16+ required (you have $(node -v))"
    exit 1
fi

echo "✅ Node.js $(node -v) detected"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
npm install

if [ $? -ne 0 ]; then
    echo "❌ Error installing dependencies"
    exit 1
fi

echo "✅ Dependencies installed"
echo ""

# Setup environment file
if [ ! -f .env ]; then
    echo "🔧 Setting up environment configuration..."
    cp .env.example .env
    echo "✅ Created .env file from template"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env to add your AI provider API key"
    echo "   For example: OPENAI_API_KEY=sk-..."
    echo ""
else
    echo "✅ Environment file already exists"
fi

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/medical_records
mkdir -p data/rag_index
mkdir -p data/memory
mkdir -p data/backup
echo "✅ Data directories created"
echo ""

# Initialize database
echo "🗜️ Initializing database..."
npx prisma generate
npx prisma db push

if [ $? -ne 0 ]; then
    echo "❌ Error initializing database"
    exit 1
fi

echo "✅ Database initialized"
echo ""

# Success message
echo "==============================================="
echo "🎉 Installation Complete!"
echo "==============================================="
echo ""
echo "Dr. Glitter Mane is ready to serve as your AI clinical consultant."
echo ""
echo "Next steps:"
echo "1. Edit .env to add your AI provider API key"
echo "2. Run 'npm start' to launch Dr. Glitter Mane"
echo "3. Open http://localhost:3333 in your browser"
echo ""
echo "🦄 Remember: Always consult with healthcare providers for medical decisions."
echo ""