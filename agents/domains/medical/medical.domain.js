/**
 * Medical Domain Configuration
 * Healthcare AI agents orchestrated by Dr. Glitter Mane
 * Part of the Unicorn Command & Control Platform
 */

module.exports = {
  domain: {
    id: 'medical',
    name: 'Medical Domain',
    description: 'Comprehensive healthcare AI consultation and specialist network',
    icon: '🏥',
    color: '#10B981', // Medical green
    status: 'active',
    version: '1.0.0'
  },

  orchestrator: {
    id: 'dr_glitter_mane',
    name: 'Dr. Glitter Mane',
    title: 'AI Clinical Maestro & Primary Care Orchestrator',
    avatar: '🦄💉',
    role: 'primary_care_orchestrator',
    description: 'Internal medicine specialist who coordinates care across all medical specialties',
    capabilities: [
      'primary_care_consultation',
      'symptom_triage',
      'specialist_referral',
      'care_coordination',
      'medical_record_management',
      'treatment_planning',
      'preventive_care',
      'chronic_disease_management'
    ],
    specialties: [
      'internal_medicine',
      'family_medicine',
      'preventive_care',
      'geriatrics'
    ],
    canRefer: true,
    canCoordinate: true,
    baseUrl: 'http://localhost:3333', // Standalone instance
    apiEndpoint: '/api/chat'
  },

  specialists: [
    {
      id: 'dr_neuro_sparkle',
      name: 'Dr. Neuro Sparkle',
      title: 'Neurologist',
      avatar: '🧠✨',
      specialties: ['neurology', 'headache', 'epilepsy', 'stroke', 'dementia'],
      capabilities: [
        'neurological_assessment',
        'eeg_interpretation',
        'mri_brain_analysis',
        'headache_management',
        'seizure_disorders',
        'movement_disorders',
        'cognitive_assessment'
      ]
    },
    {
      id: 'dr_cardio_thunder',
      name: 'Dr. Cardio Thunder',
      title: 'Cardiologist',
      avatar: '❤️⚡',
      specialties: ['cardiology', 'electrophysiology', 'interventional'],
      capabilities: [
        'cardiac_assessment',
        'ekg_interpretation',
        'echo_analysis',
        'arrhythmia_management',
        'heart_failure_management',
        'preventive_cardiology',
        'cardiac_catheterization_planning'
      ]
    },
    {
      id: 'dr_psyche_rainbow',
      name: 'Dr. Psyche Rainbow',
      title: 'Psychiatrist',
      avatar: '🧘‍♀️🌈',
      specialties: ['psychiatry', 'psychology', 'behavioral_health'],
      capabilities: [
        'mental_health_assessment',
        'depression_treatment',
        'anxiety_management',
        'psychopharmacology',
        'therapy_recommendations',
        'crisis_intervention',
        'addiction_medicine'
      ]
    },
    {
      id: 'dr_ortho_steel',
      name: 'Dr. Ortho Steel',
      title: 'Orthopedic Surgeon',
      avatar: '🦴🔧',
      specialties: ['orthopedics', 'sports_medicine', 'spine'],
      capabilities: [
        'musculoskeletal_assessment',
        'fracture_management',
        'joint_replacement_evaluation',
        'sports_injury_treatment',
        'spine_disorders',
        'arthritis_management',
        'surgical_planning'
      ]
    },
    {
      id: 'dr_gastro_flow',
      name: 'Dr. Gastro Flow',
      title: 'Gastroenterologist',
      avatar: '🍎💊',
      specialties: ['gastroenterology', 'hepatology', 'nutrition'],
      capabilities: [
        'gi_assessment',
        'endoscopy_interpretation',
        'ibd_management',
        'liver_disease_evaluation',
        'nutritional_counseling',
        'gerd_treatment',
        'colorectal_screening'
      ]
    },
    {
      id: 'dr_pulmo_breeze',
      name: 'Dr. Pulmo Breeze',
      title: 'Pulmonologist',
      avatar: '🫁💨',
      specialties: ['pulmonology', 'critical_care', 'sleep_medicine'],
      capabilities: [
        'respiratory_assessment',
        'asthma_management',
        'copd_treatment',
        'sleep_disorder_evaluation',
        'lung_function_testing',
        'critical_care_medicine',
        'ventilator_management'
      ]
    },
    {
      id: 'dr_endo_balance',
      name: 'Dr. Endo Balance',
      title: 'Endocrinologist',
      avatar: '⚖️🔬',
      specialties: ['endocrinology', 'diabetes', 'metabolism'],
      capabilities: [
        'diabetes_management',
        'thyroid_disorders',
        'hormone_therapy',
        'metabolic_disorders',
        'obesity_medicine',
        'osteoporosis_treatment',
        'pituitary_disorders'
      ]
    },
    {
      id: 'dr_dermis_glow',
      name: 'Dr. Dermis Glow',
      title: 'Dermatologist',
      avatar: '🌟🔬',
      specialties: ['dermatology', 'cosmetic', 'pediatric_derm'],
      capabilities: [
        'skin_assessment',
        'acne_treatment',
        'skin_cancer_screening',
        'eczema_management',
        'cosmetic_dermatology',
        'hair_loss_evaluation',
        'autoimmune_skin_disorders'
      ]
    },
    {
      id: 'dr_onco_hope',
      name: 'Dr. Onco Hope',
      title: 'Oncologist',
      avatar: '🎗️💪',
      specialties: ['oncology', 'hematology', 'radiation_oncology'],
      capabilities: [
        'cancer_diagnosis',
        'chemotherapy_planning',
        'immunotherapy_evaluation',
        'palliative_care',
        'cancer_genetics',
        'clinical_trial_matching',
        'survivorship_planning'
      ]
    },
    {
      id: 'dr_peds_sunshine',
      name: 'Dr. Peds Sunshine',
      title: 'Pediatrician',
      avatar: '👶☀️',
      specialties: ['pediatrics', 'adolescent_medicine', 'neonatology'],
      capabilities: [
        'well_child_care',
        'vaccination_schedules',
        'growth_assessment',
        'developmental_milestones',
        'childhood_illness_management',
        'adhd_evaluation',
        'adolescent_health'
      ]
    },
    {
      id: 'dr_emergency_flash',
      name: 'Dr. Emergency Flash',
      title: 'Emergency Medicine',
      avatar: '🚨⚡',
      specialties: ['emergency_medicine', 'trauma', 'critical_care'],
      capabilities: [
        'emergency_triage',
        'acute_care_management',
        'trauma_assessment',
        'resuscitation_protocols',
        'toxicology',
        'disaster_medicine',
        'rapid_diagnosis'
      ]
    },
    {
      id: 'dr_radio_vision',
      name: 'Dr. Radio Vision',
      title: 'Radiologist',
      avatar: '📡👁️',
      specialties: ['radiology', 'interventional_radiology', 'nuclear_medicine'],
      capabilities: [
        'xray_interpretation',
        'ct_scan_analysis',
        'mri_interpretation',
        'ultrasound_evaluation',
        'interventional_procedures',
        'nuclear_imaging',
        'ai_assisted_diagnosis'
      ]
    }
  ],

  referralProtocol: {
    enabled: true,
    requiresOrchestrator: true,
    urgencyLevels: [
      'emergency',    // Immediate - ED/911
      'urgent',       // Within 24-48 hours
      'soon',         // Within 1-2 weeks
      'routine',      // Within 1-3 months
      'preventive'    // Annual/scheduled
    ],
    referralReasons: [
      'specialist_expertise_needed',
      'complex_diagnosis',
      'surgical_evaluation',
      'second_opinion',
      'chronic_management',
      'emergency_care'
    ]
  },

  integrations: {
    ehr: {
      enabled: false, // Future integration
      systems: ['Epic', 'Cerner', 'Allscripts']
    },
    laboratories: {
      enabled: false, // Future integration
      providers: ['LabCorp', 'Quest', 'Hospital Labs']
    },
    pharmacy: {
      enabled: false, // Future integration
      systems: ['CVS', 'Walgreens', 'Hospital Pharmacy']
    },
    imaging: {
      enabled: false, // Future integration
      pacs: ['GE', 'Philips', 'Siemens']
    }
  },

  compliance: {
    hipaa: true,
    gdpr: true,
    stateRegulations: true,
    auditLogging: true,
    encryptionRequired: true
  },

  documentation: {
    soapNotes: true,    // Subjective, Objective, Assessment, Plan
    progressNotes: true,
    consultNotes: true,
    dischargeSummaries: true,
    referralLetters: true
  },

  qualityMetrics: {
    patientSatisfaction: true,
    clinicalOutcomes: true,
    readmissionRates: true,
    preventiveCareCompliance: true,
    medicationAdherence: true
  },

  emergencyProtocols: {
    redFlags: [
      'chest_pain',
      'difficulty_breathing',
      'stroke_symptoms',
      'severe_bleeding',
      'loss_of_consciousness',
      'severe_allergic_reaction',
      'suicidal_ideation'
    ],
    autoEscalation: true,
    emergencyContact: '911'
  },

  metadata: {
    created: new Date().toISOString(),
    version: '1.0.0',
    author: 'UC2 Platform',
    lastUpdated: new Date().toISOString()
  }
};