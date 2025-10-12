/**
 * OSINT Service
 * Open Source Intelligence gathering and analysis capabilities
 */

const { PrismaClient } = require('@prisma/client');
const aiProviders = require('./aiProviders');
const fetch = require('node-fetch');

const prisma = new PrismaClient();

class OSINTService {
  constructor() {
    this.searxngUrl = process.env.SEARXNG_URL || 'http://localhost:13050';
    this.supportedEngines = [
      'google', 'bing', 'duckduckgo', 'startpage', 'searx',
      'reddit', 'twitter', 'linkedin', 'github', 'stackoverflow',
      'wikipedia', 'wikidata', 'archive_org', 'piratebay',
      'youtube', 'vimeo', 'dailymotion', 'soundcloud'
    ];
    
    this.searchCategories = {
      'general': ['google', 'bing', 'duckduckgo'],
      'social': ['reddit', 'twitter', 'linkedin'],
      'tech': ['github', 'stackoverflow'],
      'media': ['youtube', 'vimeo', 'dailymotion'],
      'academic': ['wikipedia', 'wikidata', 'archive_org'],
      'news': ['google_news', 'bing_news'],
      'images': ['google_images', 'bing_images'],
      'files': ['google_scholar', 'archive_org']
    };

    this.investigationTemplates = {
      'person': {
        name: 'Person Investigation',
        searches: [
          '"{name}"',
          '"{name}" {location}',
          '"{name}" linkedin',
          '"{name}" facebook',
          '"{name}" twitter',
          '"{name}" arrest',
          '"{name}" lawsuit',
          '"{name}" company',
          'site:linkedin.com "{name}"',
          'site:facebook.com "{name}"',
          'site:twitter.com "{name}"'
        ],
        categories: ['general', 'social', 'news']
      },
      'company': {
        name: 'Company Investigation', 
        searches: [
          '"{company_name}"',
          '"{company_name}" SEC filing',
          '"{company_name}" lawsuit',
          '"{company_name}" executives',
          '"{company_name}" scandal',
          '"{company_name}" investigation',
          'site:sec.gov "{company_name}"',
          'site:bbb.org "{company_name}"',
          'filetype:pdf "{company_name}"'
        ],
        categories: ['general', 'news', 'files']
      },
      'email': {
        name: 'Email Investigation',
        searches: [
          '"{email}"',
          '"{email}" breach',
          '"{email}" leak',
          'site:haveibeenpwned.com "{email}"',
          'site:linkedin.com "{email}"',
          'site:github.com "{email}"'
        ],
        categories: ['general', 'tech']
      },
      'phone': {
        name: 'Phone Number Investigation', 
        searches: [
          '"{phone}"',
          '"{phone}" scam',
          '"{phone}" spam',
          '"{phone}" owner',
          'site:whitepages.com "{phone}"',
          'site:truecaller.com "{phone}"'
        ],
        categories: ['general']
      },
      'domain': {
        name: 'Domain Investigation',
        searches: [
          '"{domain}"',
          '"{domain}" whois',
          '"{domain}" owner',
          '"{domain}" history',
          'site:whois.net "{domain}"',
          'site:archive.org "{domain}"'
        ],
        categories: ['general', 'tech']
      }
    };
  }

  // Perform OSINT search using SearxNG
  async search(query, options = {}) {
    try {
      const {
        engines = ['google', 'bing', 'duckduckgo'],
        category = 'general',
        language = 'en',
        time_range = '',
        safe_search = 1,
        format = 'json',
        max_results = 20
      } = options;

      // Check if Center-Deep is available
      const centerDeepAvailable = await this.checkCenterDeepAvailability();
      
      if (!centerDeepAvailable) {
        throw new Error('Center-Deep OSINT service is not available. Please ensure it is running on port 13050.');
      }

      // Build search URL
      const searchParams = new URLSearchParams({
        q: query,
        engines: engines.join(','),
        language: language,
        time_range: time_range,
        safesearch: safe_search,
        format: format
      });

      const response = await fetch(`${this.searxngUrl}/search?${searchParams}`, {
        method: 'GET',
        headers: {
          'User-Agent': 'Crisis-Management-OSINT/1.0',
          'Accept': 'application/json'
        },
        timeout: 30000
      });

      if (!response.ok) {
        throw new Error(`Center-Deep request failed: ${response.statusText}`);
      }

      const data = await response.json();
      
      return {
        success: true,
        query: query,
        engines_used: engines,
        results: data.results?.slice(0, max_results) || [],
        suggestions: data.suggestions || [],
        total_results: data.number_of_results || 0,
        search_time: data.search_time || 0,
        timestamp: new Date().toISOString()
      };

    } catch (error) {
      console.error('OSINT search error:', error);
      throw new Error(`OSINT search failed: ${error.message}`);
    }
  }

  // Check Center-Deep availability
  async checkCenterDeepAvailability() {
    try {
      const response = await fetch(`${this.searxngUrl}/stats`, {
        method: 'GET',
        timeout: 5000
      });
      return response.ok;
    } catch (error) {
      console.log('Center-Deep not available on port 13050');
      return false;
    }
  }

  // Get available search engines from Center-Deep
  async getAvailableEngines() {
    try {
      const response = await fetch(`${this.searxngUrl}/engines`, {
        method: 'GET',
        timeout: 5000
      });
      
      if (response.ok) {
        const data = await response.json();
        return data.engines || this.getDefaultEngines();
      }
    } catch (error) {
      console.error('Error fetching engines from Center-Deep:', error);
    }
    
    return this.getDefaultEngines();
  }

  // Fallback engine list
  getDefaultEngines() {
    return this.supportedEngines.map(engine => ({
      id: engine,
      name: engine.charAt(0).toUpperCase() + engine.slice(1),
      icon: this.getEngineIcon(engine),
      categories: Object.keys(this.searchCategories).filter(cat => 
        this.searchCategories[cat].includes(engine)
      )
    }));
  }

  getEngineIcon(engine) {
    const icons = {
      'google': '🔍',
      'bing': '🟦',
      'duckduckgo': '🦆',
      'reddit': '🤖',
      'twitter': '🐦',
      'linkedin': '💼',
      'github': '🐙',
      'stackoverflow': '📚',
      'wikipedia': '📖',
      'youtube': '📺',
      'archive_org': '📚'
    };
    return icons[engine] || '🔍';
  }

  // Automated investigation using templates
  async investigateTarget(target_type, target_data, options = {}) {
    try {
      const template = this.investigationTemplates[target_type];
      if (!template) {
        throw new Error(`Unknown investigation type: ${target_type}`);
      }

      const {
        caseId,
        max_results_per_search = 10,
        include_ai_analysis = true
      } = options;

      const results = {
        target_type,
        target_data,
        template_used: template.name,
        searches: [],
        summary: null,
        entities: [],
        threats: [],
        recommendations: []
      };

      // Perform searches based on template
      for (const searchTemplate of template.searches) {
        // Replace placeholders with actual data
        let query = searchTemplate;
        Object.keys(target_data).forEach(key => {
          query = query.replace(`{${key}}`, target_data[key]);
        });

        const searchResult = await this.search(query, {
          engines: this.getEnginesForCategories(template.categories),
          max_results: max_results_per_search
        });

        results.searches.push({
          query,
          ...searchResult
        });

        // Small delay to be respectful to search engines
        await new Promise(resolve => setTimeout(resolve, 1000));
      }

      // AI-powered analysis of results
      if (include_ai_analysis) {
        try {
          const analysis = await this.analyzeOSINTResults(results);
          results.summary = analysis.summary;
          results.entities = analysis.entities;
          results.threats = analysis.threats;
          results.recommendations = analysis.recommendations;
        } catch (error) {
          console.error('AI analysis failed:', error);
          results.summary = 'AI analysis unavailable - raw search results only';
          results.entities = [];
          results.threats = [];
          results.recommendations = ['Review search results manually', 'Consider additional targeted searches'];
        }
      }

      // Save investigation to database if caseId provided
      if (caseId) {
        await this.saveInvestigation(caseId, results);
      }

      return results;

    } catch (error) {
      console.error('Investigation error:', error);
      throw error;
    }
  }

  // Get engines for specified categories
  getEnginesForCategories(categories) {
    const engines = new Set();
    categories.forEach(category => {
      if (this.searchCategories[category]) {
        this.searchCategories[category].forEach(engine => engines.add(engine));
      }
    });
    return Array.from(engines);
  }

  // AI-powered analysis of OSINT results
  async analyzeOSINTResults(results) {
    try {
      // Compile all search results into text
      const allResults = results.searches
        .flatMap(search => search.results || [])
        .map(result => `Title: ${result.title}\nURL: ${result.url}\nContent: ${result.content}`)
        .join('\n\n');

      const prompt = `Analyze these OSINT search results for a ${results.target_type} investigation:

Target: ${JSON.stringify(results.target_data)}

Search Results:
${allResults}

Provide analysis in the following format:

SUMMARY:
[2-3 sentence summary of key findings]

ENTITIES:
[List important people, organizations, locations, dates found]

THREATS:
[List potential security, legal, or reputational risks identified]

RECOMMENDATIONS:
[List specific next steps for further investigation]

Focus on factual information and avoid speculation. Highlight any inconsistencies or red flags.`;

      const messages = [
        {
          role: 'system',
          content: 'You are an expert OSINT analyst specializing in open source intelligence gathering and threat assessment. Provide factual, objective analysis based on the provided data.'
        },
        {
          role: 'user',
          content: prompt
        }
      ];

      let response;
      try {
        response = await aiProviders.sendMessage('ollama', 'llama3.1:8b', messages, {
          temperature: 0.2,
          maxTokens: 1500
        });
      } catch (error) {
        // Return basic analysis structure
        return {
          summary: 'AI analysis unavailable - raw search results collected',
          entities: [],
          threats: [],
          recommendations: ['Review search results manually', 'Consider additional targeted searches']
        };
      }

      return this.parseAnalysisResponse(response.content);

    } catch (error) {
      console.error('OSINT analysis error:', error);
      return {
        summary: 'Analysis failed - raw search results available',
        entities: [],
        threats: [],
        recommendations: ['Review search results manually']
      };
    }
  }

  // Parse AI analysis response
  parseAnalysisResponse(analysisText) {
    const sections = {
      summary: '',
      entities: [],
      threats: [],
      recommendations: []
    };

    const lines = analysisText.split('\n');
    let currentSection = '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('SUMMARY:')) {
        currentSection = 'summary';
        sections.summary = trimmed.replace('SUMMARY:', '').trim();
      } else if (trimmed.startsWith('ENTITIES:')) {
        currentSection = 'entities';
      } else if (trimmed.startsWith('THREATS:')) {
        currentSection = 'threats';
      } else if (trimmed.startsWith('RECOMMENDATIONS:')) {
        currentSection = 'recommendations';
      } else if (trimmed.startsWith('-') || trimmed.startsWith('•')) {
        const item = trimmed.substring(1).trim();
        if (currentSection === 'entities') {
          sections.entities.push(item);
        } else if (currentSection === 'threats') {
          sections.threats.push(item);
        } else if (currentSection === 'recommendations') {
          sections.recommendations.push(item);
        }
      } else if (trimmed && currentSection === 'summary') {
        sections.summary += ' ' + trimmed;
      }
    }

    return sections;
  }


  // Save investigation to database
  async saveInvestigation(caseId, investigationData) {
    try {
      const investigation = await prisma.oSINTInvestigation.create({
        data: {
          caseId,
          targetType: investigationData.target_type,
          targetData: JSON.stringify(investigationData.target_data),
          results: JSON.stringify(investigationData),
          summary: investigationData.summary,
          status: 'COMPLETED',
          metadata: JSON.stringify({
            total_searches: investigationData.searches.length,
            total_results: investigationData.searches.reduce((sum, s) => sum + (s.results?.length || 0), 0),
            entities_found: investigationData.entities?.length || 0,
            threats_identified: investigationData.threats?.length || 0
          })
        }
      });

      return investigation;
    } catch (error) {
      console.error('Error saving OSINT investigation:', error);
      throw error;
    }
  }

  // Get available investigation templates
  getInvestigationTemplates() {
    return Object.keys(this.investigationTemplates).map(key => ({
      type: key,
      ...this.investigationTemplates[key]
    }));
  }

}

module.exports = new OSINTService();