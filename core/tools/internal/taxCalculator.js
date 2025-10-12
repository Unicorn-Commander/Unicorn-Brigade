const NodeCache = require('node-cache');

class TaxCalculator {
    constructor() {
        this.cache = new NodeCache({ stdTTL: 86400 }); // 24 hour cache
        this.currentTaxYear = new Date().getFullYear();

        // 2024 Federal Tax Brackets (US)
        this.federalBrackets = {
            single: [
                { min: 0, max: 11000, rate: 0.10 },
                { min: 11000, max: 44725, rate: 0.12 },
                { min: 44725, max: 95375, rate: 0.22 },
                { min: 95375, max: 182050, rate: 0.24 },
                { min: 182050, max: 231250, rate: 0.32 },
                { min: 231250, max: 578125, rate: 0.35 },
                { min: 578125, max: Infinity, rate: 0.37 }
            ],
            marriedJoint: [
                { min: 0, max: 22000, rate: 0.10 },
                { min: 22000, max: 89450, rate: 0.12 },
                { min: 89450, max: 190750, rate: 0.22 },
                { min: 190750, max: 364200, rate: 0.24 },
                { min: 364200, max: 462500, rate: 0.32 },
                { min: 462500, max: 693750, rate: 0.35 },
                { min: 693750, max: Infinity, rate: 0.37 }
            ],
            marriedSeparate: [
                { min: 0, max: 11000, rate: 0.10 },
                { min: 11000, max: 44725, rate: 0.12 },
                { min: 44725, max: 95375, rate: 0.22 },
                { min: 95375, max: 182050, rate: 0.24 },
                { min: 182050, max: 231250, rate: 0.32 },
                { min: 231250, max: 346875, rate: 0.35 },
                { min: 346875, max: Infinity, rate: 0.37 }
            ],
            headOfHousehold: [
                { min: 0, max: 15700, rate: 0.10 },
                { min: 15700, max: 59850, rate: 0.12 },
                { min: 59850, max: 95350, rate: 0.22 },
                { min: 95350, max: 182050, rate: 0.24 },
                { min: 182050, max: 231250, rate: 0.32 },
                { min: 231250, max: 578100, rate: 0.35 },
                { min: 578100, max: Infinity, rate: 0.37 }
            ]
        };

        // Standard Deductions 2024
        this.standardDeductions = {
            single: 14600,
            marriedJoint: 29200,
            marriedSeparate: 14600,
            headOfHousehold: 21900
        };

        // State tax rates (simplified - top marginal rates)
        this.stateTaxRates = {
            'AL': 5.0, 'AK': 0.0, 'AZ': 4.5, 'AR': 5.5, 'CA': 13.3,
            'CO': 4.4, 'CT': 6.99, 'DE': 6.6, 'FL': 0.0, 'GA': 5.75,
            'HI': 11.0, 'ID': 6.0, 'IL': 4.95, 'IN': 3.23, 'IA': 8.53,
            'KS': 5.7, 'KY': 5.0, 'LA': 6.0, 'ME': 7.15, 'MD': 5.75,
            'MA': 5.0, 'MI': 4.25, 'MN': 9.85, 'MS': 5.0, 'MO': 5.3,
            'MT': 6.75, 'NE': 6.84, 'NV': 0.0, 'NH': 0.0, 'NJ': 10.75,
            'NM': 5.9, 'NY': 10.9, 'NC': 4.75, 'ND': 2.9, 'OH': 3.99,
            'OK': 5.0, 'OR': 9.9, 'PA': 3.07, 'RI': 5.99, 'SC': 7.0,
            'SD': 0.0, 'TN': 0.0, 'TX': 0.0, 'UT': 4.85, 'VT': 8.75,
            'VA': 5.75, 'WA': 0.0, 'WV': 6.5, 'WI': 7.65, 'WY': 0.0
        };

        // Capital gains tax rates
        this.capitalGainsRates = {
            short_term: 'ordinary_income', // Taxed as ordinary income
            long_term: {
                single: [
                    { min: 0, max: 44625, rate: 0.0 },
                    { min: 44625, max: 492300, rate: 0.15 },
                    { min: 492300, max: Infinity, rate: 0.20 }
                ],
                marriedJoint: [
                    { min: 0, max: 89250, rate: 0.0 },
                    { min: 89250, max: 553850, rate: 0.15 },
                    { min: 553850, max: Infinity, rate: 0.20 }
                ]
            }
        };

        // FICA rates
        this.ficaRates = {
            social_security: { rate: 0.062, wage_base: 160200 },
            medicare: { rate: 0.0145, wage_base: Infinity },
            additional_medicare: { rate: 0.009, threshold_single: 200000, threshold_joint: 250000 }
        };
    }

    calculateIncomeTax(grossIncome, filingStatus = 'single', state = null, deductions = null) {
        try {
            const cacheKey = `income_tax_${grossIncome}_${filingStatus}_${state}_${deductions}`;
            const cached = this.cache.get(cacheKey);
            if (cached) return cached;

            // Use standard deduction if not provided
            const totalDeductions = deductions || this.standardDeductions[filingStatus];
            const taxableIncome = Math.max(0, grossIncome - totalDeductions);

            // Calculate federal tax
            const federalTax = this.calculateProgressiveTax(taxableIncome, this.federalBrackets[filingStatus]);

            // Calculate state tax
            let stateTax = 0;
            if (state && this.stateTaxRates[state]) {
                stateTax = taxableIncome * (this.stateTaxRates[state] / 100);
            }

            // Calculate FICA taxes
            const ficaTaxes = this.calculateFicaTaxes(grossIncome, filingStatus);

            const totalTax = federalTax + stateTax + ficaTaxes.total;
            const afterTaxIncome = grossIncome - totalTax;
            const effectiveTaxRate = (totalTax / grossIncome) * 100;
            const marginalTaxRate = this.getMarginalTaxRate(taxableIncome, this.federalBrackets[filingStatus]);

            const result = {
                calculation_type: 'Income Tax Calculation',
                tax_year: this.currentTaxYear,
                gross_income: grossIncome,
                filing_status: filingStatus,
                total_deductions: totalDeductions,
                taxable_income: taxableIncome,
                federal_tax: Math.round(federalTax * 100) / 100,
                state_tax: Math.round(stateTax * 100) / 100,
                fica_taxes: {
                    social_security: Math.round(ficaTaxes.social_security * 100) / 100,
                    medicare: Math.round(ficaTaxes.medicare * 100) / 100,
                    additional_medicare: Math.round(ficaTaxes.additional_medicare * 100) / 100,
                    total: Math.round(ficaTaxes.total * 100) / 100
                },
                total_tax: Math.round(totalTax * 100) / 100,
                after_tax_income: Math.round(afterTaxIncome * 100) / 100,
                effective_tax_rate: Math.round(effectiveTaxRate * 100) / 100,
                marginal_tax_rate: Math.round(marginalTaxRate * 100) / 100,
                tax_breakdown: this.getTaxBracketBreakdown(taxableIncome, this.federalBrackets[filingStatus]),
                calculated_at: new Date().toISOString()
            };

            this.cache.set(cacheKey, result);
            return result;

        } catch (error) {
            return {
                error: 'Income tax calculation failed',
                message: error.message,
                calculated_at: new Date().toISOString()
            };
        }
    }

    calculateCapitalGainsTax(capitalGains, ordinaryIncome, filingStatus = 'single', holdingPeriod = 'long_term') {
        try {
            let capitalGainsTax = 0;

            if (holdingPeriod === 'short_term') {
                // Short-term gains taxed as ordinary income
                const combinedIncome = ordinaryIncome + capitalGains;
                const combinedTax = this.calculateProgressiveTax(combinedIncome, this.federalBrackets[filingStatus]);
                const ordinaryTax = this.calculateProgressiveTax(ordinaryIncome, this.federalBrackets[filingStatus]);
                capitalGainsTax = combinedTax - ordinaryTax;
            } else {
                // Long-term capital gains tax
                const brackets = this.capitalGainsRates.long_term[filingStatus] || this.capitalGainsRates.long_term.single;
                capitalGainsTax = this.calculateProgressiveTax(capitalGains, brackets);
            }

            // Net Investment Income Tax (NIIT) - 3.8% on investment income
            let niitTax = 0;
            const niitThreshold = filingStatus === 'marriedJoint' ? 250000 : 200000;
            if (ordinaryIncome + capitalGains > niitThreshold) {
                const excessIncome = Math.min(capitalGains, (ordinaryIncome + capitalGains) - niitThreshold);
                niitTax = excessIncome * 0.038;
            }

            const totalCapitalGainsTax = capitalGainsTax + niitTax;
            const effectiveRate = capitalGains > 0 ? (totalCapitalGainsTax / capitalGains) * 100 : 0;

            return {
                calculation_type: 'Capital Gains Tax',
                capital_gains: capitalGains,
                ordinary_income: ordinaryIncome,
                holding_period: holdingPeriod,
                filing_status: filingStatus,
                capital_gains_tax: Math.round(capitalGainsTax * 100) / 100,
                niit_tax: Math.round(niitTax * 100) / 100,
                total_capital_gains_tax: Math.round(totalCapitalGainsTax * 100) / 100,
                effective_capital_gains_rate: Math.round(effectiveRate * 100) / 100,
                tax_savings_long_vs_short: holdingPeriod === 'long_term' ?
                    this.calculateShortTermTaxSavings(capitalGains, ordinaryIncome, filingStatus) : null,
                calculated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Capital gains tax calculation failed',
                message: error.message,
                calculated_at: new Date().toISOString()
            };
        }
    }

    calculateBusinessTax(revenue, expenses, businessType = 'sole_proprietorship', state = null) {
        try {
            const netIncome = revenue - expenses;
            let businessTax = 0;
            let selfEmploymentTax = 0;

            if (businessType === 'sole_proprietorship' || businessType === 'single_member_llc') {
                // Self-employment tax (Social Security + Medicare)
                const seTaxableIncome = netIncome * 0.9235; // 92.35% of net earnings
                selfEmploymentTax = Math.min(seTaxableIncome, this.ficaRates.social_security.wage_base) * 0.124 +
                                   seTaxableIncome * 0.029;

                // Deduction for half of self-employment tax
                const seDeduction = selfEmploymentTax / 2;
                const adjustedIncome = netIncome - seDeduction;

                businessTax = adjustedIncome; // Will be taxed as ordinary income

            } else if (businessType === 'c_corporation') {
                // Corporate tax rate is 21%
                businessTax = netIncome * 0.21;
            } else if (businessType === 's_corporation' || businessType === 'partnership') {
                // Pass-through entity - no entity-level tax
                businessTax = 0; // Tax passes through to owners
            }

            // State business tax (simplified)
            let stateTax = 0;
            if (state && this.stateTaxRates[state] && businessType === 'c_corporation') {
                stateTax = netIncome * (this.stateTaxRates[state] / 100) * 0.8; // Approximate corporate rate
            }

            // QBI Deduction for pass-through entities
            let qbiDeduction = 0;
            if (['sole_proprietorship', 's_corporation', 'partnership', 'single_member_llc'].includes(businessType)) {
                qbiDeduction = Math.min(netIncome * 0.20, 50000); // Simplified calculation
            }

            return {
                calculation_type: 'Business Tax Calculation',
                business_type: businessType,
                revenue: revenue,
                expenses: expenses,
                net_income: netIncome,
                federal_business_tax: Math.round(businessTax * 100) / 100,
                self_employment_tax: Math.round(selfEmploymentTax * 100) / 100,
                state_business_tax: Math.round(stateTax * 100) / 100,
                qbi_deduction: Math.round(qbiDeduction * 100) / 100,
                total_business_taxes: Math.round((businessTax + selfEmploymentTax + stateTax) * 100) / 100,
                effective_tax_rate: netIncome > 0 ?
                    Math.round(((businessTax + selfEmploymentTax + stateTax) / netIncome) * 10000) / 100 : 0,
                tax_planning_tips: this.getBusinessTaxTips(businessType, netIncome),
                calculated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Business tax calculation failed',
                message: error.message,
                calculated_at: new Date().toISOString()
            };
        }
    }

    calculateRetirementTaxes(withdrawalAmount, accountType, currentAge, filingStatus = 'single') {
        try {
            let taxableAmount = 0;
            let penaltyAmount = 0;
            let withholdingRate = 0;

            if (accountType === '401k' || accountType === 'traditional_ira') {
                // Traditional accounts - fully taxable
                taxableAmount = withdrawalAmount;

                // Early withdrawal penalty
                if (currentAge < 59.5) {
                    penaltyAmount = withdrawalAmount * 0.10;
                }

                // Required withholding
                withholdingRate = 0.20; // 20% federal withholding required

            } else if (accountType === 'roth_ira' || accountType === 'roth_401k') {
                // Roth accounts - contributions not taxable, earnings may be
                const assumedEarningsRatio = 0.4; // Assume 40% of account is earnings

                if (currentAge < 59.5) {
                    taxableAmount = withdrawalAmount * assumedEarningsRatio;
                    penaltyAmount = taxableAmount * 0.10;
                } else {
                    taxableAmount = 0; // Qualified distributions are tax-free
                }
            }

            // Calculate taxes on taxable amount
            const incomeTax = this.calculateProgressiveTax(taxableAmount, this.federalBrackets[filingStatus]);
            const totalTax = incomeTax + penaltyAmount;
            const netWithdrawal = withdrawalAmount - totalTax;
            const suggestedWithholding = withdrawalAmount * withholdingRate;

            return {
                calculation_type: 'Retirement Account Tax Calculation',
                withdrawal_amount: withdrawalAmount,
                account_type: accountType,
                current_age: currentAge,
                filing_status: filingStatus,
                taxable_amount: Math.round(taxableAmount * 100) / 100,
                income_tax: Math.round(incomeTax * 100) / 100,
                early_withdrawal_penalty: Math.round(penaltyAmount * 100) / 100,
                total_taxes_penalties: Math.round(totalTax * 100) / 100,
                net_withdrawal: Math.round(netWithdrawal * 100) / 100,
                suggested_withholding: Math.round(suggestedWithholding * 100) / 100,
                effective_tax_rate: withdrawalAmount > 0 ?
                    Math.round((totalTax / withdrawalAmount) * 10000) / 100 : 0,
                retirement_tax_strategies: this.getRetirementTaxStrategies(accountType, currentAge),
                calculated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Retirement tax calculation failed',
                message: error.message,
                calculated_at: new Date().toISOString()
            };
        }
    }

    calculateProgressiveTax(income, brackets) {
        let tax = 0;

        for (const bracket of brackets) {
            const taxableInThisBracket = Math.min(
                Math.max(income - bracket.min, 0),
                bracket.max - bracket.min
            );

            tax += taxableInThisBracket * bracket.rate;

            if (income <= bracket.max) break;
        }

        return tax;
    }

    calculateFicaTaxes(income, filingStatus) {
        const socialSecurityTax = Math.min(income, this.ficaRates.social_security.wage_base) *
                                 this.ficaRates.social_security.rate;

        const medicareTax = income * this.ficaRates.medicare.rate;

        const additionalMedicareThreshold = filingStatus === 'marriedJoint' ?
                                          this.ficaRates.additional_medicare.threshold_joint :
                                          this.ficaRates.additional_medicare.threshold_single;

        const additionalMedicareTax = income > additionalMedicareThreshold ?
                                    (income - additionalMedicareThreshold) * this.ficaRates.additional_medicare.rate : 0;

        return {
            social_security: socialSecurityTax,
            medicare: medicareTax,
            additional_medicare: additionalMedicareTax,
            total: socialSecurityTax + medicareTax + additionalMedicareTax
        };
    }

    getMarginalTaxRate(income, brackets) {
        for (const bracket of brackets) {
            if (income >= bracket.min && income < bracket.max) {
                return bracket.rate * 100;
            }
        }
        return brackets[brackets.length - 1].rate * 100;
    }

    getTaxBracketBreakdown(income, brackets) {
        const breakdown = [];

        for (const bracket of brackets) {
            const taxableInThisBracket = Math.min(
                Math.max(income - bracket.min, 0),
                bracket.max - bracket.min
            );

            if (taxableInThisBracket > 0) {
                breakdown.push({
                    rate: bracket.rate * 100,
                    min_income: bracket.min,
                    max_income: bracket.max === Infinity ? 'No limit' : bracket.max,
                    taxable_income: Math.round(taxableInThisBracket * 100) / 100,
                    tax_amount: Math.round(taxableInThisBracket * bracket.rate * 100) / 100
                });
            }

            if (income <= bracket.max) break;
        }

        return breakdown;
    }

    calculateShortTermTaxSavings(capitalGains, ordinaryIncome, filingStatus) {
        const shortTermTax = this.calculateProgressiveTax(capitalGains, this.federalBrackets[filingStatus]);
        const longTermTax = this.calculateProgressiveTax(capitalGains, this.capitalGainsRates.long_term[filingStatus]);
        const savings = shortTermTax - longTermTax;

        return {
            short_term_tax: Math.round(shortTermTax * 100) / 100,
            long_term_tax: Math.round(longTermTax * 100) / 100,
            tax_savings: Math.round(savings * 100) / 100,
            savings_percentage: capitalGains > 0 ? Math.round((savings / capitalGains) * 10000) / 100 : 0
        };
    }

    getBusinessTaxTips(businessType, netIncome) {
        const tips = [
            'Track all business expenses for maximum deductions',
            'Consider retirement plan contributions to reduce taxable income'
        ];

        if (businessType === 'sole_proprietorship' && netIncome > 50000) {
            tips.push('Consider forming an LLC or S-Corp for potential tax savings');
        }

        if (netIncome > 100000) {
            tips.push('Explore Section 199A QBI deduction opportunities');
            tips.push('Consider income timing strategies');
        }

        return tips;
    }

    getRetirementTaxStrategies(accountType, currentAge) {
        const strategies = [];

        if (currentAge < 59.5) {
            strategies.push('Consider loan options instead of early withdrawals to avoid penalties');
            strategies.push('Explore hardship withdrawal exceptions if applicable');
        }

        if (accountType.includes('traditional')) {
            strategies.push('Consider Roth conversions during low-income years');
            strategies.push('Plan for required minimum distributions at age 73');
        }

        strategies.push('Coordinate withdrawals across different account types');
        strategies.push('Consider tax-loss harvesting in taxable accounts');

        return strategies;
    }

    getToolInfo() {
        return {
            name: 'Tax Calculator',
            version: '2.0.0',
            description: 'Comprehensive tax calculation and planning tools',
            author: 'UC2 System',
            capabilities: [
                'Federal income tax calculations',
                'State tax estimates',
                'Capital gains tax planning',
                'Business tax calculations',
                'Retirement account tax analysis',
                'FICA tax calculations',
                'Tax bracket analysis',
                'Progressive tax modeling',
                'Self-employment tax',
                'Tax planning strategies'
            ],
            supported_filing_status: ['single', 'marriedJoint', 'marriedSeparate', 'headOfHousehold'],
            supported_business_types: ['sole_proprietorship', 'c_corporation', 's_corporation', 'partnership', 'single_member_llc'],
            tax_year: this.currentTaxYear,
            cache_duration: '24 hours'
        };
    }
}

module.exports = TaxCalculator;