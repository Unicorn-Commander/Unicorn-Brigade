const NodeCache = require('node-cache');

class FinancialCalculator {
    constructor() {
        this.cache = new NodeCache({ stdTTL: 3600 }); // 1 hour cache
        this.inflationRates = {
            'US': 3.2, 'CA': 2.8, 'UK': 4.1, 'EU': 2.4,
            'JP': 1.1, 'AU': 3.5, 'CH': 1.8, 'SE': 2.1
        };
        this.taxRates = {
            'US': { federal: 22, state: 5, capital_gains: 15 },
            'CA': { federal: 26, provincial: 8, capital_gains: 13 },
            'UK': { income: 20, capital_gains: 20, corporation: 19 },
            'EU': { average: 25, capital_gains: 15, vat: 20 }
        };
    }

    calculateCompoundInterest(principal, annualRate, compoundingPeriods, years) {
        try {
            if (principal <= 0 || annualRate < 0 || years <= 0 || compoundingPeriods <= 0) {
                throw new Error('Invalid input parameters');
            }

            const rate = annualRate / 100;
            const periodicRate = rate / compoundingPeriods;
            const totalPeriods = compoundingPeriods * years;

            const futureValue = principal * Math.pow(1 + periodicRate, totalPeriods);
            const totalInterest = futureValue - principal;
            const effectiveRate = Math.pow(1 + periodicRate, compoundingPeriods) - 1;

            return {
                calculation_type: 'Compound Interest',
                principal: principal,
                annual_rate: annualRate,
                compounding_periods: compoundingPeriods,
                years: years,
                future_value: Math.round(futureValue * 100) / 100,
                total_interest: Math.round(totalInterest * 100) / 100,
                effective_annual_rate: Math.round(effectiveRate * 10000) / 100,
                total_return_percentage: Math.round((totalInterest / principal) * 10000) / 100,
                yearly_breakdown: this.generateYearlyBreakdown(principal, periodicRate, compoundingPeriods, years),
                calculated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Compound interest calculation failed',
                message: error.message,
                calculated_at: new Date().toISOString()
            };
        }
    }

    calculateLoanPayment(principal, annualRate, years, paymentFrequency = 12) {
        try {
            if (principal <= 0 || annualRate < 0 || years <= 0) {
                throw new Error('Invalid loan parameters');
            }

            const monthlyRate = (annualRate / 100) / paymentFrequency;
            const totalPayments = years * paymentFrequency;

            let monthlyPayment;
            if (annualRate === 0) {
                monthlyPayment = principal / totalPayments;
            } else {
                monthlyPayment = principal * (monthlyRate * Math.pow(1 + monthlyRate, totalPayments)) /
                               (Math.pow(1 + monthlyRate, totalPayments) - 1);
            }

            const totalPaid = monthlyPayment * totalPayments;
            const totalInterest = totalPaid - principal;

            const amortizationSchedule = this.generateAmortizationSchedule(
                principal, monthlyRate, monthlyPayment, totalPayments
            );

            return {
                calculation_type: 'Loan Payment',
                loan_amount: principal,
                annual_rate: annualRate,
                loan_term_years: years,
                payment_frequency: paymentFrequency,
                monthly_payment: Math.round(monthlyPayment * 100) / 100,
                total_payments: totalPayments,
                total_amount_paid: Math.round(totalPaid * 100) / 100,
                total_interest_paid: Math.round(totalInterest * 100) / 100,
                interest_percentage: Math.round((totalInterest / principal) * 10000) / 100,
                amortization_schedule: amortizationSchedule.slice(0, 12), // First year
                full_schedule_available: true,
                calculated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Loan payment calculation failed',
                message: error.message,
                calculated_at: new Date().toISOString()
            };
        }
    }

    calculateMortgage(homePrice, downPaymentPercent, annualRate, years, pmi = null, taxes = 0, insurance = 0) {
        try {
            const downPayment = homePrice * (downPaymentPercent / 100);
            const loanAmount = homePrice - downPayment;

            // Base loan payment
            const loanPayment = this.calculateLoanPayment(loanAmount, annualRate, years);

            // Additional monthly costs
            const monthlyTaxes = taxes / 12;
            const monthlyInsurance = insurance / 12;
            const monthlyPMI = (downPaymentPercent < 20 && pmi) ? pmi : 0;

            const totalMonthlyPayment = loanPayment.monthly_payment + monthlyTaxes + monthlyInsurance + monthlyPMI;

            // Affordability analysis
            const recommendedIncome = totalMonthlyPayment * 12 / 0.28; // 28% rule
            const dtiRatio = totalMonthlyPayment * 12 / 50000; // Assuming 50k income for ratio

            return {
                calculation_type: 'Mortgage Analysis',
                home_price: homePrice,
                down_payment_percent: downPaymentPercent,
                down_payment_amount: Math.round(downPayment * 100) / 100,
                loan_amount: Math.round(loanAmount * 100) / 100,
                annual_rate: annualRate,
                loan_term_years: years,
                principal_interest: Math.round(loanPayment.monthly_payment * 100) / 100,
                monthly_taxes: Math.round(monthlyTaxes * 100) / 100,
                monthly_insurance: Math.round(monthlyInsurance * 100) / 100,
                monthly_pmi: Math.round(monthlyPMI * 100) / 100,
                total_monthly_payment: Math.round(totalMonthlyPayment * 100) / 100,
                total_interest_over_life: Math.round(loanPayment.total_interest_paid * 100) / 100,
                total_cost_of_home: Math.round((loanPayment.total_amount_paid + downPayment) * 100) / 100,
                recommended_annual_income: Math.round(recommendedIncome * 100) / 100,
                debt_to_income_ratio: Math.round(dtiRatio * 10000) / 100,
                loan_to_value_ratio: Math.round((loanAmount / homePrice) * 10000) / 100,
                calculated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Mortgage calculation failed',
                message: error.message,
                calculated_at: new Date().toISOString()
            };
        }
    }

    calculateRetirementSavings(currentAge, retirementAge, currentSavings, monthlyContribution, annualReturn, inflationRate = 3) {
        try {
            const yearsToRetirement = retirementAge - currentAge;
            if (yearsToRetirement <= 0) {
                throw new Error('Retirement age must be greater than current age');
            }

            const monthlyReturn = annualReturn / 100 / 12;
            const totalMonths = yearsToRetirement * 12;

            // Future value of current savings
            const futureCurrentSavings = currentSavings * Math.pow(1 + (annualReturn / 100), yearsToRetirement);

            // Future value of monthly contributions (annuity)
            const futureContributions = monthlyContribution *
                ((Math.pow(1 + monthlyReturn, totalMonths) - 1) / monthlyReturn);

            const totalRetirementSavings = futureCurrentSavings + futureContributions;
            const totalContributed = currentSavings + (monthlyContribution * totalMonths);
            const totalGrowth = totalRetirementSavings - totalContributed;

            // Adjust for inflation
            const inflationAdjustedValue = totalRetirementSavings / Math.pow(1 + (inflationRate / 100), yearsToRetirement);

            // Monthly retirement income (4% withdrawal rule)
            const monthlyRetirementIncome = (totalRetirementSavings * 0.04) / 12;
            const inflationAdjustedIncome = (inflationAdjustedValue * 0.04) / 12;

            return {
                calculation_type: 'Retirement Planning',
                current_age: currentAge,
                retirement_age: retirementAge,
                years_to_retirement: yearsToRetirement,
                current_savings: currentSavings,
                monthly_contribution: monthlyContribution,
                annual_return_rate: annualReturn,
                inflation_rate: inflationRate,
                future_value_current_savings: Math.round(futureCurrentSavings * 100) / 100,
                future_value_contributions: Math.round(futureContributions * 100) / 100,
                total_retirement_savings: Math.round(totalRetirementSavings * 100) / 100,
                total_contributed: Math.round(totalContributed * 100) / 100,
                total_investment_growth: Math.round(totalGrowth * 100) / 100,
                inflation_adjusted_value: Math.round(inflationAdjustedValue * 100) / 100,
                monthly_retirement_income: Math.round(monthlyRetirementIncome * 100) / 100,
                inflation_adjusted_income: Math.round(inflationAdjustedIncome * 100) / 100,
                replacement_ratio_needed: '70-90%',
                savings_rate_recommendation: '15-20%',
                calculated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Retirement calculation failed',
                message: error.message,
                calculated_at: new Date().toISOString()
            };
        }
    }

    calculateInvestmentROI(initialInvestment, finalValue, timeHorizonYears, additionalContributions = 0) {
        try {
            const totalInvested = initialInvestment + additionalContributions;
            const totalReturn = finalValue - totalInvested;
            const totalROIPercent = (totalReturn / totalInvested) * 100;

            // Annualized return calculation
            const annualizedReturn = (Math.pow(finalValue / totalInvested, 1 / timeHorizonYears) - 1) * 100;

            // Risk-adjusted metrics (assuming some benchmark and volatility)
            const benchmarkReturn = 7; // S&P 500 historical average
            const estimatedVolatility = Math.abs(annualizedReturn - benchmarkReturn) + 10;
            const sharpeRatio = (annualizedReturn - 2) / estimatedVolatility; // Assuming 2% risk-free rate

            return {
                calculation_type: 'Investment ROI Analysis',
                initial_investment: initialInvestment,
                additional_contributions: additionalContributions,
                total_invested: totalInvested,
                final_value: finalValue,
                time_horizon_years: timeHorizonYears,
                total_return: Math.round(totalReturn * 100) / 100,
                total_roi_percent: Math.round(totalROIPercent * 100) / 100,
                annualized_return: Math.round(annualizedReturn * 100) / 100,
                compound_annual_growth_rate: Math.round(annualizedReturn * 100) / 100,
                estimated_volatility: Math.round(estimatedVolatility * 100) / 100,
                sharpe_ratio: Math.round(sharpeRatio * 1000) / 1000,
                benchmark_comparison: {
                    benchmark_return: benchmarkReturn,
                    outperformance: Math.round((annualizedReturn - benchmarkReturn) * 100) / 100,
                    risk_adjusted_performance: sharpeRatio > 1 ? 'Excellent' : sharpeRatio > 0.5 ? 'Good' : 'Poor'
                },
                calculated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'ROI calculation failed',
                message: error.message,
                calculated_at: new Date().toISOString()
            };
        }
    }

    calculateNetPresentValue(cashFlows, discountRate) {
        try {
            if (!Array.isArray(cashFlows) || cashFlows.length === 0) {
                throw new Error('Cash flows must be a non-empty array');
            }

            let npv = 0;
            const rate = discountRate / 100;

            for (let i = 0; i < cashFlows.length; i++) {
                const presentValue = cashFlows[i] / Math.pow(1 + rate, i);
                npv += presentValue;
            }

            // Calculate IRR approximation using Newton's method
            let irr = this.calculateIRR(cashFlows);

            const paybackPeriod = this.calculatePaybackPeriod(cashFlows);
            const profitabilityIndex = npv / Math.abs(cashFlows[0]);

            return {
                calculation_type: 'Net Present Value Analysis',
                cash_flows: cashFlows,
                discount_rate: discountRate,
                net_present_value: Math.round(npv * 100) / 100,
                internal_rate_of_return: Math.round(irr * 10000) / 100,
                payback_period: paybackPeriod,
                profitability_index: Math.round(profitabilityIndex * 1000) / 1000,
                investment_decision: npv > 0 ? 'Accept' : 'Reject',
                risk_assessment: this.assessInvestmentRisk(npv, irr, discountRate),
                calculated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'NPV calculation failed',
                message: error.message,
                calculated_at: new Date().toISOString()
            };
        }
    }

    calculateBreakEven(fixedCosts, variableCostPerUnit, pricePerUnit) {
        try {
            if (pricePerUnit <= variableCostPerUnit) {
                throw new Error('Price per unit must be greater than variable cost per unit');
            }

            const contributionMargin = pricePerUnit - variableCostPerUnit;
            const contributionMarginRatio = (contributionMargin / pricePerUnit) * 100;
            const breakEvenUnits = fixedCosts / contributionMargin;
            const breakEvenRevenue = breakEvenUnits * pricePerUnit;

            // Scenario analysis
            const scenarios = [
                { name: 'Conservative', price: pricePerUnit * 0.9, units: Math.round(fixedCosts / (pricePerUnit * 0.9 - variableCostPerUnit)) },
                { name: 'Optimistic', price: pricePerUnit * 1.1, units: Math.round(fixedCosts / (pricePerUnit * 1.1 - variableCostPerUnit)) },
                { name: 'Pessimistic', price: pricePerUnit * 0.8, units: Math.round(fixedCosts / (pricePerUnit * 0.8 - variableCostPerUnit)) }
            ];

            return {
                calculation_type: 'Break-Even Analysis',
                fixed_costs: fixedCosts,
                variable_cost_per_unit: variableCostPerUnit,
                price_per_unit: pricePerUnit,
                contribution_margin: Math.round(contributionMargin * 100) / 100,
                contribution_margin_ratio: Math.round(contributionMarginRatio * 100) / 100,
                break_even_units: Math.round(breakEvenUnits),
                break_even_revenue: Math.round(breakEvenRevenue * 100) / 100,
                safety_margin_analysis: {
                    target_units: Math.round(breakEvenUnits * 1.2),
                    safety_margin: '20%',
                    recommended_price: Math.round((fixedCosts / (breakEvenUnits * 0.8) + variableCostPerUnit) * 100) / 100
                },
                scenario_analysis: scenarios,
                calculated_at: new Date().toISOString()
            };

        } catch (error) {
            return {
                error: 'Break-even calculation failed',
                message: error.message,
                calculated_at: new Date().toISOString()
            };
        }
    }

    generateYearlyBreakdown(principal, periodicRate, compoundingPeriods, years) {
        const breakdown = [];
        let currentBalance = principal;

        for (let year = 1; year <= years; year++) {
            const startBalance = currentBalance;
            for (let period = 0; period < compoundingPeriods; period++) {
                currentBalance *= (1 + periodicRate);
            }
            const yearlyInterest = currentBalance - startBalance;

            breakdown.push({
                year: year,
                starting_balance: Math.round(startBalance * 100) / 100,
                interest_earned: Math.round(yearlyInterest * 100) / 100,
                ending_balance: Math.round(currentBalance * 100) / 100
            });
        }

        return breakdown.slice(0, 10); // Return first 10 years
    }

    generateAmortizationSchedule(principal, monthlyRate, monthlyPayment, totalPayments) {
        const schedule = [];
        let remainingBalance = principal;

        for (let payment = 1; payment <= Math.min(totalPayments, 60); payment++) { // Limit to 5 years for display
            const interestPayment = remainingBalance * monthlyRate;
            const principalPayment = monthlyPayment - interestPayment;
            remainingBalance -= principalPayment;

            schedule.push({
                payment_number: payment,
                monthly_payment: Math.round(monthlyPayment * 100) / 100,
                principal_payment: Math.round(principalPayment * 100) / 100,
                interest_payment: Math.round(interestPayment * 100) / 100,
                remaining_balance: Math.round(Math.max(remainingBalance, 0) * 100) / 100
            });

            if (remainingBalance <= 0) break;
        }

        return schedule;
    }

    calculateIRR(cashFlows) {
        // Simple IRR approximation using bisection method
        let lowRate = -0.99;
        let highRate = 5.0;
        let irr = 0.1; // Initial guess

        for (let i = 0; i < 50; i++) {
            let npv = 0;
            for (let j = 0; j < cashFlows.length; j++) {
                npv += cashFlows[j] / Math.pow(1 + irr, j);
            }

            if (Math.abs(npv) < 0.001) break;

            if (npv > 0) {
                lowRate = irr;
            } else {
                highRate = irr;
            }
            irr = (lowRate + highRate) / 2;
        }

        return irr;
    }

    calculatePaybackPeriod(cashFlows) {
        let cumulativeCashFlow = 0;
        for (let i = 0; i < cashFlows.length; i++) {
            cumulativeCashFlow += cashFlows[i];
            if (cumulativeCashFlow >= 0) {
                return Math.round((i + (Math.abs(cumulativeCashFlow - cashFlows[i]) / cashFlows[i])) * 100) / 100;
            }
        }
        return 'Never';
    }

    assessInvestmentRisk(npv, irr, discountRate) {
        if (npv > 0 && irr > discountRate * 2) return 'Low Risk - Strong Investment';
        if (npv > 0 && irr > discountRate) return 'Moderate Risk - Good Investment';
        if (npv > 0) return 'High Risk - Marginal Investment';
        return 'Very High Risk - Poor Investment';
    }

    getToolInfo() {
        return {
            name: 'Financial Calculator',
            version: '2.0.0',
            description: 'Comprehensive financial calculations and analysis tools',
            author: 'UC2 System',
            capabilities: [
                'Compound interest calculations',
                'Loan payment analysis',
                'Mortgage calculations',
                'Retirement planning',
                'Investment ROI analysis',
                'Net Present Value (NPV)',
                'Internal Rate of Return (IRR)',
                'Break-even analysis',
                'Amortization schedules',
                'Scenario modeling'
            ],
            supported_calculations: [
                'Compound Interest', 'Loan Payments', 'Mortgages',
                'Retirement Savings', 'Investment ROI', 'NPV/IRR',
                'Break-Even Analysis', 'Cash Flow Analysis'
            ],
            cache_duration: '1 hour'
        };
    }
}

module.exports = FinancialCalculator;