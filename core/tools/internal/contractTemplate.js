const fs = require('fs').promises;
const path = require('path');

class ContractTemplateTool {
    constructor() {
        this.name = 'contractTemplate';
        this.version = '1.0.0';
        this.description = 'Generate and customize legal contract templates';
        this.category = 'Legal Research';
        this.author = 'UC2 System';
        this.tags = ['legal', 'contracts', 'templates', 'automation', 'drafting'];

        this.schema = {
            type: 'object',
            properties: {
                contractType: {
                    type: 'string',
                    description: 'Type of contract to generate',
                    enum: [
                        'nda',                    // Non-disclosure agreement
                        'employment',             // Employment contract
                        'service-agreement',      // Service agreement
                        'consultant',            // Consultant agreement
                        'license',               // License agreement
                        'lease',                 // Lease agreement
                        'purchase',              // Purchase agreement
                        'loan',                  // Loan agreement
                        'partnership',           // Partnership agreement
                        'vendor',                // Vendor agreement
                        'settlement',            // Settlement agreement
                        'retainer',              // Legal retainer agreement
                        'custom'                 // Custom contract
                    ]
                },
                jurisdiction: {
                    type: 'string',
                    description: 'Legal jurisdiction for the contract',
                    enum: ['california', 'new-york', 'texas', 'florida', 'federal', 'delaware', 'nevada', 'international'],
                    default: 'california'
                },
                parties: {
                    type: 'array',
                    description: 'Contract parties information',
                    items: {
                        type: 'object',
                        properties: {
                            name: { type: 'string', description: 'Party name' },
                            type: {
                                type: 'string',
                                enum: ['individual', 'corporation', 'llc', 'partnership', 'nonprofit'],
                                description: 'Type of entity'
                            },
                            address: { type: 'string', description: 'Full address' },
                            role: { type: 'string', description: 'Role in contract (e.g., employer, contractor)' },
                            email: { type: 'string', format: 'email', description: 'Email address' },
                            phone: { type: 'string', description: 'Phone number' },
                            taxId: { type: 'string', description: 'Tax ID or SSN (last 4 digits)' }
                        },
                        required: ['name', 'type', 'address', 'role']
                    },
                    minItems: 2,
                    maxItems: 10
                },
                terms: {
                    type: 'object',
                    description: 'Contract terms and conditions',
                    properties: {
                        duration: {
                            type: 'string',
                            description: 'Contract duration (e.g., "1 year", "indefinite", "project-based")'
                        },
                        compensation: {
                            type: 'object',
                            properties: {
                                amount: { type: 'number', description: 'Payment amount' },
                                currency: { type: 'string', default: 'USD' },
                                frequency: {
                                    type: 'string',
                                    enum: ['hourly', 'daily', 'weekly', 'monthly', 'annually', 'project-based', 'lump-sum']
                                },
                                schedule: { type: 'string', description: 'Payment schedule details' }
                            }
                        },
                        deliverables: {
                            type: 'array',
                            items: { type: 'string' },
                            description: 'Contract deliverables or outcomes'
                        },
                        responsibilities: {
                            type: 'object',
                            description: 'Responsibilities by party',
                            additionalProperties: {
                                type: 'array',
                                items: { type: 'string' }
                            }
                        },
                        confidentiality: {
                            type: 'boolean',
                            description: 'Include confidentiality clauses',
                            default: true
                        },
                        nonCompete: {
                            type: 'object',
                            properties: {
                                included: { type: 'boolean', default: false },
                                duration: { type: 'string', description: 'Non-compete duration' },
                                scope: { type: 'string', description: 'Geographic or industry scope' }
                            }
                        },
                        intellectualProperty: {
                            type: 'object',
                            properties: {
                                ownership: {
                                    type: 'string',
                                    enum: ['client', 'contractor', 'shared', 'case-by-case']
                                },
                                exceptions: {
                                    type: 'array',
                                    items: { type: 'string' }
                                }
                            }
                        },
                        termination: {
                            type: 'object',
                            properties: {
                                notice: { type: 'string', description: 'Termination notice period' },
                                causes: {
                                    type: 'array',
                                    items: { type: 'string' },
                                    description: 'Grounds for termination'
                                },
                                procedures: { type: 'string', description: 'Termination procedures' }
                            }
                        }
                    }
                },
                customClauses: {
                    type: 'array',
                    description: 'Custom clauses to include',
                    items: {
                        type: 'object',
                        properties: {
                            title: { type: 'string', description: 'Clause title' },
                            content: { type: 'string', description: 'Clause content' },
                            position: {
                                type: 'string',
                                enum: ['beginning', 'middle', 'end', 'after-terms'],
                                default: 'middle'
                            }
                        },
                        required: ['title', 'content']
                    }
                },
                outputFormat: {
                    type: 'string',
                    description: 'Output format for the contract',
                    enum: ['docx', 'pdf', 'markdown', 'html', 'txt'],
                    default: 'docx'
                },
                includeSchedules: {
                    type: 'boolean',
                    description: 'Include placeholder schedules/exhibits',
                    default: true
                },
                legalReview: {
                    type: 'boolean',
                    description: 'Include legal review checklist',
                    default: true
                },
                compliance: {
                    type: 'array',
                    description: 'Compliance requirements to address',
                    items: {
                        type: 'string',
                        enum: ['gdpr', 'ccpa', 'hipaa', 'sox', 'pci-dss', 'ferpa', 'ada']
                    }
                }
            },
            required: ['contractType', 'parties']
        };

        // Contract templates by type
        this.templates = {
            nda: {
                name: 'Non-Disclosure Agreement',
                sections: ['preamble', 'definitions', 'confidential-info', 'obligations', 'exclusions', 'term', 'remedies', 'general'],
                requiredTerms: ['duration', 'confidentiality']
            },
            employment: {
                name: 'Employment Agreement',
                sections: ['preamble', 'position', 'compensation', 'benefits', 'duties', 'confidentiality', 'termination', 'general'],
                requiredTerms: ['compensation', 'responsibilities', 'termination']
            },
            'service-agreement': {
                name: 'Service Agreement',
                sections: ['preamble', 'services', 'compensation', 'deliverables', 'timeline', 'ip-ownership', 'termination', 'general'],
                requiredTerms: ['deliverables', 'compensation', 'intellectualProperty']
            },
            consultant: {
                name: 'Consultant Agreement',
                sections: ['preamble', 'services', 'compensation', 'independent-contractor', 'confidentiality', 'ip-ownership', 'termination', 'general'],
                requiredTerms: ['deliverables', 'compensation', 'intellectualProperty']
            },
            settlement: {
                name: 'Settlement Agreement',
                sections: ['preamble', 'recitals', 'settlement-terms', 'releases', 'confidentiality', 'compliance', 'enforcement', 'general'],
                requiredTerms: ['compensation', 'confidentiality']
            }
        };

        // Jurisdiction-specific clauses
        this.jurisdictionClauses = {
            california: {
                governingLaw: 'This Agreement shall be governed by and construed in accordance with the laws of the State of California.',
                dispute: 'Any disputes shall be resolved in the courts of California.',
                specialProvisions: ['California Labor Code compliance', 'CCPA compliance if applicable']
            },
            'new-york': {
                governingLaw: 'This Agreement shall be governed by and construed in accordance with the laws of the State of New York.',
                dispute: 'Any disputes shall be resolved in the courts of New York.',
                specialProvisions: ['New York Labor Law compliance']
            },
            federal: {
                governingLaw: 'This Agreement shall be governed by and construed in accordance with federal law.',
                dispute: 'Any disputes shall be resolved in federal court.',
                specialProvisions: ['Federal employment law compliance']
            }
        };

        // Compliance templates
        this.complianceTemplates = {
            gdpr: {
                clauses: ['Data processing terms', 'Individual rights', 'Data breach notification'],
                requirements: ['Lawful basis for processing', 'Data subject rights', 'Privacy by design']
            },
            hipaa: {
                clauses: ['PHI protection', 'Business associate provisions', 'Security safeguards'],
                requirements: ['Administrative safeguards', 'Physical safeguards', 'Technical safeguards']
            },
            ccpa: {
                clauses: ['Consumer privacy rights', 'Data sharing restrictions', 'Opt-out mechanisms'],
                requirements: ['Right to know', 'Right to delete', 'Right to opt-out']
            }
        };

        // Cache for generated contracts
        this.cache = new Map();
        this.cacheTimeout = 30 * 60 * 1000; // 30 minutes
    }

    async execute(params) {
        const startTime = Date.now();

        try {
            this.validateParams(params);

            const result = {
                success: true,
                contractType: params.contractType,
                jurisdiction: params.jurisdiction || 'california',
                parties: params.parties,
                timestamp: new Date().toISOString(),
                contract: null,
                metadata: {
                    version: this.version,
                    template: null,
                    sections: [],
                    wordCount: 0,
                    pageEstimate: 0,
                    executionTime: null
                },
                legalReview: null,
                compliance: null
            };

            // Check cache
            const cacheKey = this.generateCacheKey(params);
            const cached = this.getFromCache(cacheKey);
            if (cached) {
                result.contract = cached.contract;
                result.metadata = { ...result.metadata, ...cached.metadata, cached: true };
                result.legalReview = cached.legalReview;
                result.metadata.executionTime = `${Date.now() - startTime}ms`;
                return result;
            }

            // Generate contract
            const template = this.templates[params.contractType];
            if (!template) {
                throw new Error(`Unknown contract type: ${params.contractType}`);
            }

            result.metadata.template = template.name;
            result.metadata.sections = template.sections;

            // Build contract content
            const contractBuilder = new ContractBuilder(params, template, this.jurisdictionClauses);
            const contractContent = await contractBuilder.build();

            result.contract = contractContent;
            result.metadata.wordCount = this.countWords(contractContent.content);
            result.metadata.pageEstimate = Math.ceil(result.metadata.wordCount / 250);

            // Add legal review checklist if requested
            if (params.legalReview) {
                result.legalReview = this.generateLegalReviewChecklist(params, template);
            }

            // Add compliance information if requested
            if (params.compliance && params.compliance.length > 0) {
                result.compliance = this.generateComplianceInfo(params.compliance);
            }

            // Cache result
            this.setCache(cacheKey, {
                contract: result.contract,
                metadata: result.metadata,
                legalReview: result.legalReview
            });

            result.metadata.executionTime = `${Date.now() - startTime}ms`;
            return result;

        } catch (error) {
            return {
                success: false,
                error: error.message,
                contractType: params.contractType,
                executionTime: `${Date.now() - startTime}ms`
            };
        }
    }

    validateParams(params) {
        if (!params.contractType) {
            throw new Error('Contract type is required');
        }

        if (!this.templates[params.contractType]) {
            throw new Error(`Unsupported contract type: ${params.contractType}`);
        }

        if (!params.parties || !Array.isArray(params.parties) || params.parties.length < 2) {
            throw new Error('At least two parties are required');
        }

        // Validate party information
        for (const party of params.parties) {
            if (!party.name || !party.type || !party.address || !party.role) {
                throw new Error('Each party must have name, type, address, and role');
            }

            if (party.email && !this.isValidEmail(party.email)) {
                throw new Error(`Invalid email address for party: ${party.name}`);
            }
        }

        // Validate required terms for contract type
        const template = this.templates[params.contractType];
        if (template.requiredTerms && params.terms) {
            for (const requiredTerm of template.requiredTerms) {
                if (!params.terms[requiredTerm]) {
                    throw new Error(`Required term missing: ${requiredTerm}`);
                }
            }
        }
    }

    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    generateLegalReviewChecklist(params, template) {
        const checklist = {
            contractType: template.name,
            reviewPoints: [],
            riskAssessment: 'medium',
            requiredActions: [],
            recommendations: []
        };

        // General review points
        checklist.reviewPoints = [
            'Verify all party information is accurate and complete',
            'Confirm jurisdiction and governing law are appropriate',
            'Review all financial terms for accuracy',
            'Ensure termination clauses are balanced and fair',
            'Verify compliance with applicable laws and regulations'
        ];

        // Contract-specific review points
        switch (params.contractType) {
            case 'employment':
                checklist.reviewPoints.push(
                    'Verify compliance with employment laws',
                    'Review non-compete and confidentiality terms',
                    'Confirm benefit and compensation accuracy',
                    'Check at-will employment implications'
                );
                break;
            case 'nda':
                checklist.reviewPoints.push(
                    'Define confidential information clearly',
                    'Set appropriate duration for obligations',
                    'Include adequate carve-outs and exceptions',
                    'Specify remedies for breach'
                );
                break;
            case 'service-agreement':
                checklist.reviewPoints.push(
                    'Clearly define scope of services',
                    'Set realistic delivery timelines',
                    'Address intellectual property ownership',
                    'Include appropriate limitation of liability'
                );
                break;
        }

        // Risk assessment
        let riskFactors = 0;
        if (params.terms?.nonCompete?.included) riskFactors++;
        if (params.terms?.compensation?.amount > 100000) riskFactors++;
        if (params.customClauses?.length > 3) riskFactors++;

        if (riskFactors >= 2) {
            checklist.riskAssessment = 'high';
            checklist.requiredActions.push('Recommend attorney review before execution');
        } else if (riskFactors === 1) {
            checklist.riskAssessment = 'medium';
            checklist.requiredActions.push('Consider attorney consultation');
        } else {
            checklist.riskAssessment = 'low';
        }

        // Recommendations
        checklist.recommendations = [
            'Have all parties review the contract carefully',
            'Keep signed copies in a secure location',
            'Set calendar reminders for key dates and renewals',
            'Consider periodic contract reviews for long-term agreements'
        ];

        return checklist;
    }

    generateComplianceInfo(complianceReqs) {
        const info = {
            requirements: [],
            additionalClauses: [],
            considerations: []
        };

        for (const req of complianceReqs) {
            const template = this.complianceTemplates[req];
            if (template) {
                info.requirements.push({
                    regulation: req.toUpperCase(),
                    clauses: template.clauses,
                    requirements: template.requirements
                });

                info.additionalClauses.push(...template.clauses);
                info.considerations.push(`Ensure ${req.toUpperCase()} compliance throughout contract term`);
            }
        }

        return info;
    }

    countWords(text) {
        return text.split(/\s+/).filter(word => word.length > 0).length;
    }

    // Cache methods
    generateCacheKey(params) {
        // Create a hash of the key parameters
        const keyData = {
            contractType: params.contractType,
            parties: params.parties?.map(p => ({ name: p.name, role: p.role })),
            terms: params.terms,
            jurisdiction: params.jurisdiction
        };
        return JSON.stringify(keyData);
    }

    getFromCache(key) {
        const cached = this.cache.get(key);
        if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
            return cached.data;
        }
        this.cache.delete(key);
        return null;
    }

    setCache(key, data) {
        this.cache.set(key, {
            data: data,
            timestamp: Date.now()
        });

        // Clean old entries
        if (this.cache.size > 20) {
            const oldestKey = this.cache.keys().next().value;
            this.cache.delete(oldestKey);
        }
    }
}

class ContractBuilder {
    constructor(params, template, jurisdictionClauses) {
        this.params = params;
        this.template = template;
        this.jurisdictionClauses = jurisdictionClauses;
        this.jurisdiction = params.jurisdiction || 'california';
    }

    async build() {
        const contract = {
            title: this.template.name,
            content: '',
            metadata: {
                created: new Date().toISOString(),
                parties: this.params.parties.length,
                sections: this.template.sections.length
            },
            sections: []
        };

        // Build each section
        for (const sectionName of this.template.sections) {
            const section = await this.buildSection(sectionName);
            contract.sections.push(section);
            contract.content += section.content + '\n\n';
        }

        // Add custom clauses
        if (this.params.customClauses) {
            for (const customClause of this.params.customClauses) {
                const section = {
                    title: customClause.title,
                    content: customClause.content,
                    type: 'custom'
                };
                contract.sections.push(section);
                contract.content += `## ${customClause.title}\n\n${customClause.content}\n\n`;
            }
        }

        // Add signature block
        const signatureSection = this.buildSignatureBlock();
        contract.sections.push(signatureSection);
        contract.content += signatureSection.content;

        return contract;
    }

    async buildSection(sectionName) {
        const section = {
            title: this.getSectionTitle(sectionName),
            content: '',
            type: sectionName
        };

        switch (sectionName) {
            case 'preamble':
                section.content = this.buildPreamble();
                break;
            case 'definitions':
                section.content = this.buildDefinitions();
                break;
            case 'services':
                section.content = this.buildServicesSection();
                break;
            case 'compensation':
                section.content = this.buildCompensationSection();
                break;
            case 'confidentiality':
            case 'confidential-info':
                section.content = this.buildConfidentialitySection();
                break;
            case 'ip-ownership':
                section.content = this.buildIPSection();
                break;
            case 'termination':
                section.content = this.buildTerminationSection();
                break;
            case 'general':
                section.content = this.buildGeneralSection();
                break;
            default:
                section.content = this.buildGenericSection(sectionName);
        }

        return section;
    }

    getSectionTitle(sectionName) {
        const titles = {
            'preamble': 'Agreement',
            'definitions': 'Definitions',
            'services': 'Services',
            'compensation': 'Compensation',
            'confidentiality': 'Confidentiality',
            'confidential-info': 'Confidential Information',
            'ip-ownership': 'Intellectual Property',
            'termination': 'Termination',
            'general': 'General Provisions'
        };
        return titles[sectionName] || sectionName.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    buildPreamble() {
        const parties = this.params.parties;
        const party1 = parties[0];
        const party2 = parties[1];

        return `# ${this.template.name}

This ${this.template.name} ("Agreement") is entered into on _____________, 202_ ("Effective Date") between:

**${party1.name}**, a ${party1.type} ${party1.address ? `located at ${party1.address}` : ''} ("${party1.role}"); and

**${party2.name}**, a ${party2.type} ${party2.address ? `located at ${party2.address}` : ''} ("${party2.role}").

WHEREAS, the parties desire to establish the terms and conditions of their business relationship;

NOW, THEREFORE, in consideration of the mutual covenants contained herein, the parties agree as follows:`;
    }

    buildDefinitions() {
        return `## 1. Definitions

For purposes of this Agreement:

(a) "Agreement" means this ${this.template.name} and all amendments, modifications, and supplements hereto.

(b) "Confidential Information" means any and all non-public, proprietary, or confidential information disclosed by one party to the other.

(c) "Effective Date" means the date first written above.

(d) "Party" or "Parties" means the parties to this Agreement individually or collectively.`;
    }

    buildServicesSection() {
        const deliverables = this.params.terms?.deliverables || ['Services to be defined'];

        let content = `## 2. Services

The ${this.params.parties[1].role} shall provide the following services:

`;

        deliverables.forEach((deliverable, index) => {
            content += `${index + 1}. ${deliverable}\n`;
        });

        if (this.params.terms?.duration) {
            content += `\nThe services shall be provided for a period of ${this.params.terms.duration}.`;
        }

        return content;
    }

    buildCompensationSection() {
        const comp = this.params.terms?.compensation;
        let content = `## 3. Compensation

`;

        if (comp) {
            if (comp.frequency === 'lump-sum') {
                content += `The ${this.params.parties[0].role} shall pay the ${this.params.parties[1].role} a total sum of ${comp.currency || 'USD'} $${comp.amount?.toLocaleString() || '[AMOUNT]'}.`;
            } else {
                content += `The ${this.params.parties[0].role} shall pay the ${this.params.parties[1].role} ${comp.currency || 'USD'} $${comp.amount?.toLocaleString() || '[AMOUNT]'} ${comp.frequency || 'as specified'}.`;
            }

            if (comp.schedule) {
                content += ` Payment terms: ${comp.schedule}.`;
            }
        } else {
            content += `Compensation terms to be agreed upon by the parties.`;
        }

        content += `\n\nAll payments shall be made within thirty (30) days of receipt of invoice.`;

        return content;
    }

    buildConfidentialitySection() {
        let content = `## 4. Confidentiality

Each party acknowledges that it may have access to confidential information of the other party. Each party agrees to:

(a) Hold all confidential information in strict confidence;
(b) Use confidential information solely for the purposes of this Agreement;
(c) Not disclose confidential information to any third party without prior written consent;
(d) Return or destroy all confidential information upon termination of this Agreement.

This obligation shall survive termination of this Agreement`;

        if (this.params.terms?.duration) {
            content += ` for a period of ${this.params.terms.duration}`;
        }

        content += `.`;

        return content;
    }

    buildIPSection() {
        const ip = this.params.terms?.intellectualProperty;
        let content = `## 5. Intellectual Property

`;

        if (ip?.ownership === 'client') {
            content += `All intellectual property created under this Agreement shall belong to the ${this.params.parties[0].role}.`;
        } else if (ip?.ownership === 'contractor') {
            content += `All intellectual property created under this Agreement shall belong to the ${this.params.parties[1].role}.`;
        } else if (ip?.ownership === 'shared') {
            content += `All intellectual property created under this Agreement shall be jointly owned by both parties.`;
        } else {
            content += `Intellectual property ownership shall be determined on a case-by-case basis as agreed by the parties.`;
        }

        if (ip?.exceptions && ip.exceptions.length > 0) {
            content += `\n\nExceptions: ${ip.exceptions.join(', ')}.`;
        }

        return content;
    }

    buildTerminationSection() {
        const term = this.params.terms?.termination;
        let content = `## 6. Termination

`;

        if (term?.notice) {
            content += `Either party may terminate this Agreement with ${term.notice} written notice.`;
        } else {
            content += `Either party may terminate this Agreement with thirty (30) days written notice.`;
        }

        if (term?.causes && term.causes.length > 0) {
            content += `\n\nThis Agreement may be terminated immediately for cause, including:\n`;
            term.causes.forEach((cause, index) => {
                content += `${index + 1}. ${cause}\n`;
            });
        }

        content += `\nUpon termination, all obligations shall cease except those that by their nature should survive termination.`;

        return content;
    }

    buildGeneralSection() {
        const jurisdictionClause = this.jurisdictionClauses[this.jurisdiction];

        return `## 7. General Provisions

**Governing Law.** ${jurisdictionClause?.governingLaw || 'This Agreement shall be governed by applicable law.'}

**Dispute Resolution.** ${jurisdictionClause?.dispute || 'Disputes shall be resolved through appropriate legal channels.'}

**Entire Agreement.** This Agreement constitutes the entire agreement between the parties and supersedes all prior negotiations, representations, or agreements.

**Amendment.** This Agreement may only be amended in writing signed by both parties.

**Severability.** If any provision of this Agreement is deemed invalid, the remainder shall remain in full force and effect.

**Assignment.** Neither party may assign this Agreement without the prior written consent of the other party.

**Force Majeure.** Neither party shall be liable for delays or failures due to circumstances beyond their reasonable control.`;
    }

    buildGenericSection(sectionName) {
        return `## ${this.getSectionTitle(sectionName)}

[Content for ${sectionName} section to be customized based on specific requirements.]`;
    }

    buildSignatureBlock() {
        const parties = this.params.parties;

        let content = `## Signatures

By signing below, the parties agree to be bound by the terms of this Agreement.

`;

        parties.forEach(party => {
            content += `**${party.name}**

By: _________________________  Date: ___________
Name: [Print Name]
Title: [Title]

`;
        });

        return {
            title: 'Signatures',
            content: content,
            type: 'signature'
        };
    }
}

module.exports = ContractTemplateTool;