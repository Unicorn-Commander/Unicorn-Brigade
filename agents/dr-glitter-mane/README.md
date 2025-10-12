# 🦄💉 Dr. Glitter Mane - AI Clinical Maestro

> *"With a dash of unicorn brilliance and a trove of medical insight, I'm here to interpret symptoms, guide your care, and help you make empowered decisions."*

## 📋 Overview

Dr. Glitter Mane is a standalone AI medical consultant powered by advanced language models and RAG (Retrieval-Augmented Generation) technology. She provides personalized medical consultations, analyzes medical records, and offers comprehensive diagnostic insights.

### ✨ Key Features

- **🏥 Medical Diagnosis** - Differential diagnosis with rare disease detection
- **📄 Document Processing** - Upload and analyze medical records, lab results, imaging
- **🔍 RAG-Powered Search** - Semantic search across all your medical documents
- **💊 Treatment Recommendations** - Evidence-based medication and treatment suggestions
- **🧪 Lab Interpretation** - Detailed analysis of laboratory test results
- **👥 Specialist Referrals** - Recommendations for appropriate specialists
- **🧠 Memory System** - Remembers your medical history across sessions
- **🔒 HIPAA-Compliant** - Secure, encrypted storage of medical information

## 🚀 Quick Start

### Prerequisites

- Node.js 16+ installed
- 2GB free disk space
- (Optional) OpenAI API key or other AI provider credentials

### Installation

```bash
# Clone or download Dr. Glitter Mane
git clone https://github.com/yourusername/dr-glitter-mane.git
cd dr-glitter-mane

# Install dependencies
npm install

# Copy environment configuration
cp .env.example .env

# Edit .env and add your AI provider API key
# For example, add your OpenAI key:
# OPENAI_API_KEY=sk-...

# Initialize database
npm run db:init

# Start Dr. Glitter Mane
npm start
```

### Access the Application

Open your browser and navigate to:
```
http://localhost:3333
```

## 🎮 Usage Guide

### 1. Starting a Consultation

1. Open the web interface at `http://localhost:3333`
2. Click "Start New Consultation"
3. Type your symptoms or medical questions
4. Dr. Glitter Mane will provide comprehensive analysis

### 2. Uploading Medical Records

1. Click the "Upload Medical Records" button
2. Drag and drop or select your files:
   - PDF documents
   - Images (JPG, PNG)
   - Text files
   - Word documents
3. Files are automatically processed and indexed
4. Your documents become searchable in future consultations

### 3. Understanding Responses

Dr. Glitter Mane provides structured responses including:

- **Summary** - Clear, conversational overview
- **Most Likely Diagnosis** - Primary diagnostic considerations
- **Other Possibilities** - Including rare conditions
- **Recommended Medications** - With alternatives and cautions
- **Suggested Tests** - Laboratory and imaging recommendations
- **Specialist Referrals** - When to seek specialized care
- **Red Flags** - Warning signs requiring immediate attention

## 🔧 Configuration

### AI Provider Options

Dr. Glitter Mane supports multiple AI providers:

#### OpenAI (Recommended)
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview
```

#### Anthropic Claude
```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-opus-20240229
```

#### OpenRouter (Multiple Models)
```env
OPENROUTER_API_KEY=sk-or-v1-000000000000000000000000000000000000
OPENROUTER_MODEL=openai/gpt-4-turbo
```

#### Local Ollama (Offline)
```env
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama2:70b
```

### Memory Configuration

Adjust memory retention in `.env`:
```env
MEMORY_HOT_TIER_DAYS=30      # Recent consultations
MEMORY_WARM_TIER_DAYS=180    # 6 months history
MEMORY_COLD_TIER_DAYS=730    # 2 years archived
```

## 📁 Project Structure

```
dr-glitter-mane/
├── backend/
│   └── server.js          # Express server with API endpoints
├── frontend/
│   └── DrGlitterMane.html # Standalone web interface
├── rag/
│   └── ragService.js      # Document processing and search
├── config/
│   └── agent.config.js    # Agent configuration
├── prisma/
│   └── schema.prisma      # Database schema
├── data/
│   ├── medical_records/   # Uploaded documents
│   ├── rag_index/         # Vector embeddings
│   └── dr_glitter_mane.db # SQLite database
├── package.json           # Dependencies
├── .env.example           # Environment template
└── README.md              # This file
```

## 🔒 Security & Privacy

- **Encryption**: All data encrypted at rest (AES-256) and in transit (TLS 1.3)
- **Local Storage**: Your medical data stays on your machine
- **No Cloud Dependency**: Can run completely offline with local AI models
- **HIPAA Considerations**: Designed with medical privacy in mind
- **Session Management**: Automatic timeout after 30 minutes of inactivity

## 🚨 Important Disclaimers

⚠️ **Medical Disclaimer**: Dr. Glitter Mane is an AI consultant and NOT a licensed medical provider. Always consult with your healthcare provider for medical decisions.

🚑 **Emergency**: In case of emergency, call 911 or your local emergency services immediately.

💊 **Medication**: Never start, stop, or change medications without consulting your doctor.

🏥 **Professional Care**: This AI is designed to supplement, not replace, professional medical care.

## 🛠️ Advanced Features

### Running with Docker

```bash
# Build the Docker image
docker build -t dr-glitter-mane .

# Run the container
docker run -d -p 3333:3333 \
  -v $(pwd)/data:/app/data \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  dr-glitter-mane
```

### Document Processing with Apache Tika

For enhanced document processing:
```bash
# Start Apache Tika server
docker run -d -p 9998:9998 apache/tika

# Add to .env
APACHE_TIKA_URL=http://localhost:9998
```

### Voice Features with LiveKit

Enable voice consultations:
```bash
# Start LiveKit server
docker run -d -p 7880:7880 livekit/livekit-server --dev

# Configure in .env
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=your-key
LIVEKIT_API_SECRET=your-secret
```

## 🐛 Troubleshooting

### Common Issues

**Port Already in Use**
```bash
# Change port in .env
PORT=3334
```

**Database Errors**
```bash
# Reset database
rm data/dr_glitter_mane.db
npm run db:init
```

**API Key Issues**
- Ensure your API key is correctly set in `.env`
- Check you have credits/quota with your AI provider
- Try switching to a different provider

**File Upload Failures**
- Check file size (default max: 100MB)
- Ensure file type is supported
- Check disk space availability

## 📊 Performance

- **Response Time**: 2-5 seconds with AI providers
- **Document Processing**: ~5 seconds per MB
- **Memory Search**: <200ms for semantic queries
- **Startup Time**: <10 seconds
- **RAM Usage**: ~500MB typical, 1GB max

## 🤝 Contributing

Dr. Glitter Mane is part of the UC2 (Unicorn Command & Control) platform. Contributions welcome!

## 📜 License

MIT License - See LICENSE file for details

## 🦄 About

Dr. Glitter Mane combines the rigor of clinical medicine with the magic of AI to provide accessible, intelligent medical guidance. While she can't replace your doctor, she's here to help you understand your health better and make more informed decisions.

---

*Built with 💜 by the UC2 Platform Team*

**Remember**: Your health is precious. Use Dr. Glitter Mane as a tool for understanding, but always seek professional medical care for health concerns.

---

### Quick Commands

```bash
# Start the application
npm start

# Development mode with auto-reload
npm run dev

# Run tests
npm test

# Database management
npm run db:init     # Initialize database
npm run db:reset    # Reset database

# Check system health
curl http://localhost:3333/api/health
```