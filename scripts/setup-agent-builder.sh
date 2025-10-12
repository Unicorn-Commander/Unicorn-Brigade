#!/bin/bash

echo "🦄 Unicorn Brigade - Agent Builder System Setup"
echo "================================================"
echo ""

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Must run from unicorn-command-control root directory"
    exit 1
fi

echo "📦 Step 1: Installing dependencies..."
npm install
if [ $? -ne 0 ]; then
    echo "❌ Failed to install backend dependencies"
    exit 1
fi

echo ""
echo "🗄️  Step 2: Running database migrations..."
npx prisma generate
npx prisma migrate dev --name add-agent-builder-system
if [ $? -ne 0 ]; then
    echo "⚠️  Migration failed or was skipped"
fi

echo ""
echo "📝 Step 3: Checking configuration files..."
if [ -f "config/agents/the-general.json" ]; then
    echo "✅ The General configuration found"
else
    echo "❌ The General configuration missing"
fi

if [ -f ".env" ]; then
    echo "✅ .env file found"

    # Check for required env variables
    if grep -q "OPENROUTER_API_KEY" .env || grep -q "LITELLM_PROXY_URL" .env; then
        echo "✅ LLM provider configured"
    else
        echo "⚠️  Warning: No LLM provider API key found in .env"
        echo "   Add OPENROUTER_API_KEY or configure LITELLM_PROXY_URL"
    fi
else
    echo "⚠️  .env file not found - using defaults"
fi

echo ""
echo "🎨 Step 4: Setting up frontend..."
cd frontend
npm install
if [ $? -ne 0 ]; then
    echo "❌ Failed to install frontend dependencies"
    exit 1
fi
cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Ensure your .env file has OPENROUTER_API_KEY or LITELLM_PROXY_URL"
echo "2. Start backend: npm run dev"
echo "3. Start frontend (in new terminal): cd frontend && npm run dev"
echo "4. Visit http://localhost:8113/builder-chat to chat with The General"
echo "5. Visit http://localhost:8113/library to view agents"
echo ""
echo "📖 For full documentation, see AGENT_BUILDER_SETUP.md"
echo ""
