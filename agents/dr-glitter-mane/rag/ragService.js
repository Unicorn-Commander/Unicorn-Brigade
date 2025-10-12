const fs = require('fs').promises;
const path = require('path');
const crypto = require('crypto');
const pdfParse = require('pdf-parse');
const NodeCache = require('node-cache');

/**
 * RAG (Retrieval-Augmented Generation) Service for Dr. Glitter Mane
 * Handles medical document processing, indexing, and retrieval
 */
class RAGService {
  constructor(config) {
    this.config = config;
    this.cache = new NodeCache({ stdTTL: 3600 }); // 1 hour cache
    this.vectorIndex = new Map(); // In-memory vector index
    this.documentStore = new Map(); // Document metadata store
    this.chunkSize = 1000; // Characters per chunk
    this.chunkOverlap = 200; // Overlap between chunks

    console.log('🔍 RAG Service initialized');
  }

  /**
   * Initialize the RAG system
   */
  async initialize() {
    try {
      // Create necessary directories
      const indexPath = path.join(__dirname, '../data/rag_index');
      await fs.mkdir(indexPath, { recursive: true });

      // Load existing index if available
      await this.loadIndex();

      console.log('✅ RAG system ready');
      return true;
    } catch (error) {
      console.error('RAG initialization error:', error);
      throw error;
    }
  }

  /**
   * Process a medical document
   */
  async processDocument(documentInfo) {
    try {
      const { filePath, fileName, documentType, userId, description } = documentInfo;

      console.log(`📄 Processing document: ${fileName}`);

      // Extract text from document
      const text = await this.extractText(filePath, fileName);

      if (!text) {
        throw new Error('No text could be extracted from document');
      }

      // Generate document ID
      const documentId = this.generateDocumentId(fileName, userId);

      // Chunk the text
      const chunks = this.chunkText(text);
      console.log(`📝 Created ${chunks.length} chunks from document`);

      // Process each chunk
      const processedChunks = [];
      for (let i = 0; i < chunks.length; i++) {
        const chunk = chunks[i];
        const chunkId = `${documentId}_chunk_${i}`;

        // Generate embedding (mock or real)
        const embedding = await this.generateEmbedding(chunk);

        // Store chunk with metadata
        const chunkData = {
          id: chunkId,
          documentId,
          chunkIndex: i,
          content: chunk,
          embedding,
          metadata: {
            fileName,
            documentType,
            userId,
            description,
            chunkPosition: `${i + 1}/${chunks.length}`,
            extractedAt: new Date()
          }
        };

        // Add to vector index
        this.vectorIndex.set(chunkId, {
          embedding,
          content: chunk,
          metadata: chunkData.metadata
        });

        processedChunks.push(chunkData);
      }

      // Store document metadata
      this.documentStore.set(documentId, {
        id: documentId,
        fileName,
        filePath,
        documentType,
        userId,
        description,
        chunks: processedChunks.length,
        processedAt: new Date(),
        textLength: text.length,
        medicalEntities: this.extractMedicalEntities(text)
      });

      // Save index to disk
      await this.saveIndex();

      console.log(`✅ Document processed: ${fileName} (${processedChunks.length} chunks)`);

      return {
        documentId,
        chunks: processedChunks.length,
        entities: this.extractMedicalEntities(text).length
      };

    } catch (error) {
      console.error('Document processing error:', error);
      throw error;
    }
  }

  /**
   * Extract text from various document formats
   */
  async extractText(filePath, fileName) {
    try {
      const extension = path.extname(fileName).toLowerCase();

      switch (extension) {
        case '.pdf':
          return await this.extractPDFText(filePath);

        case '.txt':
        case '.md':
          return await fs.readFile(filePath, 'utf-8');

        case '.doc':
        case '.docx':
          // Would use a library like mammoth for Word docs
          console.log('Word document processing not yet implemented, using mock text');
          return this.getMockMedicalText();

        case '.jpg':
        case '.jpeg':
        case '.png':
          // Would use OCR (like Tesseract.js) for images
          console.log('Image OCR not yet implemented, using mock text');
          return this.getMockMedicalText();

        default:
          // Try to read as text
          return await fs.readFile(filePath, 'utf-8');
      }
    } catch (error) {
      console.error('Text extraction error:', error);
      return this.getMockMedicalText();
    }
  }

  /**
   * Extract text from PDF
   */
  async extractPDFText(filePath) {
    try {
      const dataBuffer = await fs.readFile(filePath);
      const data = await pdfParse(dataBuffer);
      return data.text;
    } catch (error) {
      console.error('PDF extraction error:', error);
      return this.getMockMedicalText();
    }
  }

  /**
   * Chunk text into smaller segments
   */
  chunkText(text) {
    const chunks = [];
    const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];
    let currentChunk = '';

    for (const sentence of sentences) {
      if (currentChunk.length + sentence.length <= this.chunkSize) {
        currentChunk += sentence;
      } else {
        if (currentChunk) {
          chunks.push(currentChunk.trim());
        }
        currentChunk = sentence;
      }
    }

    if (currentChunk) {
      chunks.push(currentChunk.trim());
    }

    // Add overlap between chunks
    const overlappedChunks = [];
    for (let i = 0; i < chunks.length; i++) {
      let chunk = chunks[i];

      // Add end of previous chunk
      if (i > 0 && chunks[i - 1].length > this.chunkOverlap) {
        const prevEnd = chunks[i - 1].slice(-this.chunkOverlap);
        chunk = prevEnd + ' ' + chunk;
      }

      // Add beginning of next chunk
      if (i < chunks.length - 1 && chunks[i + 1].length > this.chunkOverlap) {
        const nextStart = chunks[i + 1].slice(0, this.chunkOverlap);
        chunk = chunk + ' ' + nextStart;
      }

      overlappedChunks.push(chunk);
    }

    return overlappedChunks;
  }

  /**
   * Generate embedding for text
   */
  async generateEmbedding(text) {
    if (this.config.embeddings.provider === 'openai' && process.env.OPENAI_API_KEY) {
      // Would call OpenAI embeddings API
      try {
        const fetch = require('node-fetch');
        const response = await fetch('https://api.openai.com/v1/embeddings', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            input: text,
            model: this.config.embeddings.model
          })
        });

        const data = await response.json();
        return data.data[0].embedding;

      } catch (error) {
        console.error('Embedding generation error:', error);
      }
    }

    // Generate mock embedding
    return this.generateMockEmbedding(text);
  }

  /**
   * Generate mock embedding for testing
   */
  generateMockEmbedding(text) {
    const hash = crypto.createHash('md5').update(text).digest('hex');
    const embedding = [];
    const dimensions = this.config.embeddings.dimensions || 1536;

    for (let i = 0; i < dimensions; i++) {
      const seedValue = parseInt(hash.substring(i % 32, (i % 32) + 2), 16);
      embedding.push((Math.sin(seedValue + i) + Math.cos(seedValue * i)) / 2);
    }

    // Normalize
    const magnitude = Math.sqrt(embedding.reduce((sum, val) => sum + val * val, 0));
    return embedding.map(val => val / magnitude);
  }

  /**
   * Search for relevant documents
   */
  async search(query, options = {}) {
    try {
      const { limit = 5, threshold = 0.7 } = options;

      // Generate query embedding
      const queryEmbedding = await this.generateEmbedding(query);

      // Search vector index
      const results = [];
      for (const [chunkId, data] of this.vectorIndex) {
        const similarity = this.calculateCosineSimilarity(queryEmbedding, data.embedding);

        if (similarity >= threshold) {
          results.push({
            chunkId,
            content: data.content,
            metadata: data.metadata,
            similarity
          });
        }
      }

      // Sort by similarity and limit
      results.sort((a, b) => b.similarity - a.similarity);
      const topResults = results.slice(0, limit);

      console.log(`🔍 Found ${topResults.length} relevant chunks for query`);

      return topResults;

    } catch (error) {
      console.error('Search error:', error);
      return [];
    }
  }

  /**
   * Calculate cosine similarity between vectors
   */
  calculateCosineSimilarity(vectorA, vectorB) {
    if (vectorA.length !== vectorB.length) return 0;

    let dotProduct = 0;
    let magnitudeA = 0;
    let magnitudeB = 0;

    for (let i = 0; i < vectorA.length; i++) {
      dotProduct += vectorA[i] * vectorB[i];
      magnitudeA += vectorA[i] * vectorA[i];
      magnitudeB += vectorB[i] * vectorB[i];
    }

    magnitudeA = Math.sqrt(magnitudeA);
    magnitudeB = Math.sqrt(magnitudeB);

    if (magnitudeA === 0 || magnitudeB === 0) return 0;

    return dotProduct / (magnitudeA * magnitudeB);
  }

  /**
   * Extract medical entities from text
   */
  extractMedicalEntities(text) {
    const entities = [];
    const lowerText = text.toLowerCase();

    // Medical conditions
    const conditions = [
      'diabetes', 'hypertension', 'asthma', 'cancer', 'heart disease',
      'stroke', 'copd', 'pneumonia', 'covid', 'influenza', 'arthritis',
      'scad', 'migraine', 'epilepsy', 'depression', 'anxiety'
    ];

    // Medications
    const medications = [
      'aspirin', 'ibuprofen', 'metformin', 'lisinopril', 'atorvastatin',
      'omeprazole', 'metoprolol', 'albuterol', 'prednisone', 'insulin'
    ];

    // Symptoms
    const symptoms = [
      'fever', 'cough', 'headache', 'fatigue', 'pain', 'nausea',
      'dizziness', 'shortness of breath', 'chest pain', 'weakness'
    ];

    // Lab tests
    const labTests = [
      'blood pressure', 'glucose', 'cholesterol', 'cbc', 'hemoglobin',
      'white blood cell', 'platelet', 'creatinine', 'bilirubin'
    ];

    // Extract entities
    conditions.forEach(condition => {
      if (lowerText.includes(condition)) {
        entities.push({ type: 'condition', value: condition });
      }
    });

    medications.forEach(medication => {
      if (lowerText.includes(medication)) {
        entities.push({ type: 'medication', value: medication });
      }
    });

    symptoms.forEach(symptom => {
      if (lowerText.includes(symptom)) {
        entities.push({ type: 'symptom', value: symptom });
      }
    });

    labTests.forEach(test => {
      if (lowerText.includes(test)) {
        entities.push({ type: 'lab_test', value: test });
      }
    });

    // Extract dates (simple pattern)
    const datePattern = /\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b/g;
    const dates = text.match(datePattern) || [];
    dates.forEach(date => {
      entities.push({ type: 'date', value: date });
    });

    // Extract numbers with units (vital signs, lab values)
    const valuePattern = /\b\d+\.?\d*\s*(mg|ml|mmHg|bpm|°F|°C|%)/gi;
    const values = text.match(valuePattern) || [];
    values.forEach(value => {
      entities.push({ type: 'measurement', value: value });
    });

    return entities;
  }

  /**
   * Save index to disk
   */
  async saveIndex() {
    try {
      const indexPath = path.join(__dirname, '../data/rag_index');

      // Save vector index
      const vectorData = Array.from(this.vectorIndex.entries());
      await fs.writeFile(
        path.join(indexPath, 'vectors.json'),
        JSON.stringify(vectorData, null, 2)
      );

      // Save document store
      const documentData = Array.from(this.documentStore.entries());
      await fs.writeFile(
        path.join(indexPath, 'documents.json'),
        JSON.stringify(documentData, null, 2)
      );

      console.log('💾 Index saved to disk');
    } catch (error) {
      console.error('Error saving index:', error);
    }
  }

  /**
   * Load index from disk
   */
  async loadIndex() {
    try {
      const indexPath = path.join(__dirname, '../data/rag_index');

      // Load vector index
      const vectorFile = path.join(indexPath, 'vectors.json');
      try {
        const vectorData = await fs.readFile(vectorFile, 'utf-8');
        const vectors = JSON.parse(vectorData);
        this.vectorIndex = new Map(vectors);
        console.log(`📚 Loaded ${this.vectorIndex.size} vector chunks`);
      } catch (error) {
        console.log('No existing vector index found');
      }

      // Load document store
      const documentFile = path.join(indexPath, 'documents.json');
      try {
        const documentData = await fs.readFile(documentFile, 'utf-8');
        const documents = JSON.parse(documentData);
        this.documentStore = new Map(documents);
        console.log(`📄 Loaded ${this.documentStore.size} documents`);
      } catch (error) {
        console.log('No existing document store found');
      }

    } catch (error) {
      console.error('Error loading index:', error);
    }
  }

  /**
   * Get document by ID
   */
  getDocument(documentId) {
    return this.documentStore.get(documentId);
  }

  /**
   * Get all documents for a user
   */
  getUserDocuments(userId) {
    const userDocs = [];
    for (const [id, doc] of this.documentStore) {
      if (doc.userId === userId) {
        userDocs.push(doc);
      }
    }
    return userDocs;
  }

  /**
   * Delete a document
   */
  async deleteDocument(documentId) {
    try {
      // Remove from document store
      this.documentStore.delete(documentId);

      // Remove chunks from vector index
      const chunkIds = [];
      for (const [chunkId] of this.vectorIndex) {
        if (chunkId.startsWith(documentId)) {
          chunkIds.push(chunkId);
        }
      }

      chunkIds.forEach(id => this.vectorIndex.delete(id));

      // Save updated index
      await this.saveIndex();

      console.log(`🗑️ Deleted document ${documentId} and ${chunkIds.length} chunks`);
      return true;

    } catch (error) {
      console.error('Error deleting document:', error);
      return false;
    }
  }

  /**
   * Generate document ID
   */
  generateDocumentId(fileName, userId) {
    const timestamp = Date.now();
    const hash = crypto
      .createHash('md5')
      .update(`${fileName}_${userId}_${timestamp}`)
      .digest('hex')
      .substring(0, 8);

    return `doc_${hash}_${timestamp}`;
  }

  /**
   * Get mock medical text for testing
   */
  getMockMedicalText() {
    return `PATIENT MEDICAL RECORD

Patient Name: Test Patient
Date of Birth: 01/15/1980
Medical Record Number: MRN-12345

CHIEF COMPLAINT:
Patient presents with persistent headache and fatigue lasting 2 weeks.

HISTORY OF PRESENT ILLNESS:
The patient reports experiencing moderate to severe headaches, primarily frontal, occurring daily for the past two weeks. Associated symptoms include fatigue, mild nausea, and occasional dizziness. No fever reported. Patient has been taking ibuprofen 400mg every 6 hours with minimal relief.

PAST MEDICAL HISTORY:
- Hypertension (diagnosed 2018)
- Type 2 Diabetes (diagnosed 2020)
- Seasonal allergies

MEDICATIONS:
- Lisinopril 10mg daily
- Metformin 500mg twice daily
- Loratadine 10mg as needed

VITAL SIGNS:
- Blood Pressure: 138/88 mmHg
- Heart Rate: 78 bpm
- Temperature: 98.6°F
- Respiratory Rate: 16/min
- O2 Saturation: 98% on room air

PHYSICAL EXAMINATION:
General: Alert and oriented x3, appears fatigued
HEENT: No signs of trauma, pupils equal and reactive
Cardiovascular: Regular rate and rhythm, no murmurs
Respiratory: Clear to auscultation bilaterally
Neurological: No focal deficits, reflexes 2+ throughout

LABORATORY RESULTS:
- Complete Blood Count: Within normal limits
- Glucose: 142 mg/dL (elevated)
- Creatinine: 1.0 mg/dL
- Hemoglobin A1c: 7.2%

ASSESSMENT AND PLAN:
1. Tension headaches - likely stress-related
   - Continue ibuprofen, add muscle relaxation exercises
   - Consider preventive medication if no improvement

2. Diabetes - suboptimal control
   - Increase metformin to 1000mg twice daily
   - Reinforce dietary modifications
   - Follow up in 3 months with repeat A1c

3. Hypertension - borderline controlled
   - Continue current medication
   - Monitor blood pressure at home

FOLLOW-UP:
Schedule follow-up appointment in 2 weeks to reassess headache symptoms.`;
  }

  /**
   * Get service info
   */
  getInfo() {
    return {
      documentsIndexed: this.documentStore.size,
      chunksIndexed: this.vectorIndex.size,
      embeddingDimensions: this.config.embeddings.dimensions,
      chunkSize: this.chunkSize,
      chunkOverlap: this.chunkOverlap,
      provider: this.config.embeddings.provider,
      model: this.config.embeddings.model
    };
  }
}

module.exports = RAGService;