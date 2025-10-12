const axios = require('axios');

class StockAnalyzerTool {
    constructor() {
        this.name = 'stockAnalyzer';
        this.version = '1.0.0';
        this.description = 'Real-time stock data analysis and financial market intelligence';
        this.category = 'Financial Analysis';
        this.author = 'UC2 System';
        this.tags = ['stocks', 'finance', 'market', 'analysis', 'investment'];

        this.schema = {
            type: 'object',
            properties: {
                symbol: {
                    type: 'string',
                    description: 'Stock symbol (e.g., AAPL, GOOGL, TSLA)',
                    pattern: '^[A-Za-z]{1,5}$'
                },
                operation: {
                    type: 'string',
                    description: 'Type of analysis to perform',
                    enum: [
                        'quote',           // Real-time quote
                        'history',         // Historical data
                        'profile',         // Company profile
                        'financials',      // Financial statements
                        'analysis',        // Technical analysis
                        'news',           // Recent news
                        'recommendations', // Analyst recommendations
                        'comprehensive'    // All available data
                    ],
                    default: 'quote'
                },
                period: {
                    type: 'string',
                    description: 'Time period for historical data',
                    enum: ['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'],
                    default: '1mo'
                },
                interval: {
                    type: 'string',
                    description: 'Data interval',
                    enum: ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo'],
                    default: '1d'
                },
                includeAnalysis: {
                    type: 'boolean',
                    description: 'Include technical analysis indicators',
                    default: true
                },
                currency: {
                    type: 'string',
                    description: 'Currency for financial data',
                    default: 'USD'
                }
            },
            required: ['symbol']
        };

        // Data providers (in order of preference)
        this.providers = [
            { name: 'Yahoo Finance', enabled: true, rateLimit: 2000 },
            { name: 'Alpha Vantage', enabled: false, apiKey: process.env.ALPHA_VANTAGE_KEY },
            { name: 'IEX Cloud', enabled: false, apiKey: process.env.IEX_API_KEY },
            { name: 'Finnhub', enabled: false, apiKey: process.env.FINNHUB_API_KEY }
        ];

        // Technical analysis indicators
        this.indicators = {
            sma: this.calculateSMA.bind(this),
            ema: this.calculateEMA.bind(this),
            rsi: this.calculateRSI.bind(this),
            macd: this.calculateMACD.bind(this),
            bollinger: this.calculateBollingerBands.bind(this)
        };

        // Cache for API responses (5 minutes)
        this.cache = new Map();
        this.cacheTimeout = 5 * 60 * 1000;

        this.lastRequest = 0;
        this.minInterval = 1000; // Rate limiting
    }

    async execute(params) {
        const startTime = Date.now();

        try {
            this.validateParams(params);

            const symbol = params.symbol.toUpperCase();
            const operation = params.operation || 'quote';

            // Rate limiting
            await this.rateLimitDelay();

            const result = {
                success: true,
                symbol: symbol,
                operation: operation,
                timestamp: new Date().toISOString(),
                data: {},
                metadata: {
                    version: this.version,
                    provider: null,
                    executionTime: null,
                    cached: false
                }
            };

            // Check cache first
            const cacheKey = `${symbol}-${operation}-${params.period}-${params.interval}`;
            const cached = this.getFromCache(cacheKey);
            if (cached) {
                result.data = cached;
                result.metadata.cached = true;
                result.metadata.executionTime = `${Date.now() - startTime}ms`;
                return result;
            }

            // Execute the requested operation
            switch (operation) {
                case 'quote':
                    result.data = await this.getQuote(symbol);
                    break;
                case 'history':
                    result.data = await this.getHistoricalData(symbol, params.period, params.interval);
                    break;
                case 'profile':
                    result.data = await this.getCompanyProfile(symbol);
                    break;
                case 'financials':
                    result.data = await this.getFinancials(symbol);
                    break;
                case 'analysis':
                    result.data = await this.getTechnicalAnalysis(symbol, params);
                    break;
                case 'news':
                    result.data = await this.getNews(symbol);
                    break;
                case 'recommendations':
                    result.data = await this.getRecommendations(symbol);
                    break;
                case 'comprehensive':
                    result.data = await this.getComprehensiveData(symbol, params);
                    break;
                default:
                    throw new Error(`Unknown operation: ${operation}`);
            }

            // Add technical analysis if requested
            if (params.includeAnalysis && operation !== 'analysis' && operation !== 'comprehensive') {
                if (result.data.history || result.data.historicalData) {
                    const prices = result.data.history || result.data.historicalData;
                    result.data.technicalAnalysis = this.performTechnicalAnalysis(prices);
                }
            }

            // Cache the result
            this.setCache(cacheKey, result.data);

            result.metadata.executionTime = `${Date.now() - startTime}ms`;
            return result;

        } catch (error) {
            return {
                success: false,
                error: error.message,
                symbol: params.symbol?.toUpperCase(),
                operation: params.operation,
                executionTime: `${Date.now() - startTime}ms`
            };
        }
    }

    validateParams(params) {
        if (!params.symbol) {
            throw new Error('Symbol parameter is required');
        }

        if (!/^[A-Za-z]{1,5}$/.test(params.symbol)) {
            throw new Error('Invalid symbol format. Use 1-5 letters only.');
        }
    }

    async rateLimitDelay() {
        const now = Date.now();
        const timeSinceLastRequest = now - this.lastRequest;

        if (timeSinceLastRequest < this.minInterval) {
            await new Promise(resolve =>
                setTimeout(resolve, this.minInterval - timeSinceLastRequest)
            );
        }

        this.lastRequest = Date.now();
    }

    // Yahoo Finance API methods (free tier)
    async getQuote(symbol) {
        try {
            const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}`;
            const response = await axios.get(url, {
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                timeout: 10000
            });

            const data = response.data;
            if (!data.chart.result || data.chart.result.length === 0) {
                throw new Error('No data found for symbol');
            }

            const result = data.chart.result[0];
            const meta = result.meta;
            const quote = result.indicators.quote[0];

            return {
                symbol: meta.symbol,
                price: meta.regularMarketPrice,
                change: meta.regularMarketPrice - meta.previousClose,
                changePercent: ((meta.regularMarketPrice - meta.previousClose) / meta.previousClose) * 100,
                volume: meta.regularMarketVolume,
                marketCap: meta.marketCap,
                dayRange: {
                    low: meta.regularMarketDayLow,
                    high: meta.regularMarketDayHigh
                },
                fiftyTwoWeekRange: {
                    low: meta.fiftyTwoWeekLow,
                    high: meta.fiftyTwoWeekHigh
                },
                currency: meta.currency,
                exchange: meta.exchangeName,
                marketState: meta.marketState,
                timezone: meta.timezone,
                timestamp: new Date(meta.regularMarketTime * 1000).toISOString(),
                raw: {
                    open: quote.open[quote.open.length - 1],
                    high: quote.high[quote.high.length - 1],
                    low: quote.low[quote.low.length - 1],
                    close: quote.close[quote.close.length - 1],
                    volume: quote.volume[quote.volume.length - 1]
                }
            };
        } catch (error) {
            throw new Error(`Failed to get quote: ${error.message}`);
        }
    }

    async getHistoricalData(symbol, period = '1mo', interval = '1d') {
        try {
            const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}`;
            const response = await axios.get(url, {
                params: {
                    period1: this.getPeriodStart(period),
                    period2: Math.floor(Date.now() / 1000),
                    interval: interval,
                    includePrePost: 'true',
                    events: 'div,splits'
                },
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                timeout: 15000
            });

            const data = response.data;
            if (!data.chart.result || data.chart.result.length === 0) {
                throw new Error('No historical data found');
            }

            const result = data.chart.result[0];
            const timestamps = result.timestamp;
            const indicators = result.indicators;
            const quote = indicators.quote[0];

            const historicalData = timestamps.map((timestamp, index) => ({
                date: new Date(timestamp * 1000).toISOString().split('T')[0],
                timestamp: timestamp,
                open: quote.open[index],
                high: quote.high[index],
                low: quote.low[index],
                close: quote.close[index],
                volume: quote.volume[index],
                adjClose: indicators.adjclose?.[0]?.adjclose?.[index] || quote.close[index]
            })).filter(item => item.close !== null);

            return {
                symbol: symbol,
                period: period,
                interval: interval,
                dataPoints: historicalData.length,
                historicalData: historicalData,
                summary: this.calculateHistoricalSummary(historicalData),
                events: {
                    dividends: result.events?.dividends || {},
                    splits: result.events?.splits || {}
                }
            };
        } catch (error) {
            throw new Error(`Failed to get historical data: ${error.message}`);
        }
    }

    async getCompanyProfile(symbol) {
        try {
            // Using Yahoo Finance's summary module
            const url = `https://query2.finance.yahoo.com/v10/finance/quoteSummary/${symbol}`;
            const response = await axios.get(url, {
                params: {
                    modules: 'assetProfile,summaryProfile,price,summaryDetail,defaultKeyStatistics'
                },
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                timeout: 10000
            });

            const data = response.data;
            if (!data.quoteSummary.result) {
                throw new Error('No profile data found');
            }

            const modules = data.quoteSummary.result[0];
            const profile = modules.assetProfile || {};
            const summary = modules.summaryDetail || {};
            const keyStats = modules.defaultKeyStatistics || {};

            return {
                symbol: symbol,
                companyName: profile.longName || 'N/A',
                industry: profile.industry || 'N/A',
                sector: profile.sector || 'N/A',
                website: profile.website || 'N/A',
                description: profile.longBusinessSummary || 'N/A',
                headquarters: {
                    city: profile.city || 'N/A',
                    state: profile.state || 'N/A',
                    country: profile.country || 'N/A'
                },
                employees: profile.fullTimeEmployees || 'N/A',
                keyStatistics: {
                    marketCap: keyStats.marketCap?.raw || 'N/A',
                    enterpriseValue: keyStats.enterpriseValue?.raw || 'N/A',
                    peRatio: keyStats.forwardPE?.raw || summary.forwardPE?.raw || 'N/A',
                    pegRatio: keyStats.pegRatio?.raw || 'N/A',
                    priceToBook: keyStats.priceToBook?.raw || 'N/A',
                    priceToSales: keyStats.priceToSalesTrailing12Months?.raw || 'N/A',
                    profitMargin: keyStats.profitMargins?.raw || 'N/A',
                    beta: keyStats.beta?.raw || 'N/A',
                    eps: keyStats.trailingEps?.raw || 'N/A',
                    sharesOutstanding: keyStats.sharesOutstanding?.raw || 'N/A'
                },
                governance: {
                    auditRisk: profile.auditRisk || 'N/A',
                    boardRisk: profile.boardRisk || 'N/A',
                    compensationRisk: profile.compensationRisk || 'N/A',
                    shareHolderRightsRisk: profile.shareHolderRightsRisk || 'N/A'
                }
            };
        } catch (error) {
            throw new Error(`Failed to get company profile: ${error.message}`);
        }
    }

    async getFinancials(symbol) {
        try {
            const url = `https://query2.finance.yahoo.com/v10/finance/quoteSummary/${symbol}`;
            const response = await axios.get(url, {
                params: {
                    modules: 'incomeStatementHistory,balanceSheetHistory,cashflowStatementHistory,financialData'
                },
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                timeout: 15000
            });

            const data = response.data;
            if (!data.quoteSummary.result) {
                throw new Error('No financial data found');
            }

            const modules = data.quoteSummary.result[0];

            return {
                symbol: symbol,
                financialData: modules.financialData || {},
                incomeStatement: this.processFinancialData(modules.incomeStatementHistory?.incomeStatementHistory || []),
                balanceSheet: this.processFinancialData(modules.balanceSheetHistory?.balanceSheetHistory || []),
                cashFlow: this.processFinancialData(modules.cashflowStatementHistory?.cashflowStatements || []),
                ratios: this.calculateFinancialRatios(modules.financialData || {}),
                lastUpdated: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Failed to get financials: ${error.message}`);
        }
    }

    async getTechnicalAnalysis(symbol, params) {
        const historicalData = await this.getHistoricalData(symbol, params.period, params.interval);
        return this.performTechnicalAnalysis(historicalData.historicalData);
    }

    async getNews(symbol) {
        try {
            // Using a simple news search (would be better with dedicated financial news API)
            const searchQuery = `${symbol} stock financial news`;

            return {
                symbol: symbol,
                articles: [
                    {
                        title: `Recent developments for ${symbol}`,
                        description: 'Financial news data would be available with a dedicated news API',
                        source: 'Multiple Sources',
                        publishedAt: new Date().toISOString(),
                        url: `#news-${symbol}`,
                        relevanceScore: 0.85
                    }
                ],
                note: 'Comprehensive news requires API keys for financial news services'
            };
        } catch (error) {
            throw new Error(`Failed to get news: ${error.message}`);
        }
    }

    async getRecommendations(symbol) {
        try {
            const url = `https://query2.finance.yahoo.com/v10/finance/quoteSummary/${symbol}`;
            const response = await axios.get(url, {
                params: {
                    modules: 'recommendationTrend,upgradeDowngradeHistory'
                },
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                timeout: 10000
            });

            const data = response.data;
            if (!data.quoteSummary.result) {
                return {
                    symbol: symbol,
                    recommendations: [],
                    note: 'No recommendation data available'
                };
            }

            const modules = data.quoteSummary.result[0];
            const trends = modules.recommendationTrend?.trend || [];
            const upgrades = modules.upgradeDowngradeHistory?.history || [];

            return {
                symbol: symbol,
                currentRecommendations: this.processRecommendations(trends),
                recentUpgradesDowngrades: this.processUpgradesDowngrades(upgrades),
                summary: this.summarizeRecommendations(trends)
            };
        } catch (error) {
            throw new Error(`Failed to get recommendations: ${error.message}`);
        }
    }

    async getComprehensiveData(symbol, params) {
        try {
            const [quote, history, profile, financials, news] = await Promise.all([
                this.getQuote(symbol).catch(err => ({ error: err.message })),
                this.getHistoricalData(symbol, params.period, params.interval).catch(err => ({ error: err.message })),
                this.getCompanyProfile(symbol).catch(err => ({ error: err.message })),
                this.getFinancials(symbol).catch(err => ({ error: err.message })),
                this.getNews(symbol).catch(err => ({ error: err.message }))
            ]);

            const result = {
                symbol: symbol,
                quote: quote,
                historicalData: history,
                profile: profile,
                financials: financials,
                news: news
            };

            // Add technical analysis if historical data is available
            if (history.historicalData && !history.error) {
                result.technicalAnalysis = this.performTechnicalAnalysis(history.historicalData);
            }

            // Generate investment analysis
            result.investmentAnalysis = this.generateInvestmentAnalysis(result);

            return result;
        } catch (error) {
            throw new Error(`Failed to get comprehensive data: ${error.message}`);
        }
    }

    // Technical Analysis Methods
    performTechnicalAnalysis(data) {
        if (!data || data.length < 20) {
            return { error: 'Insufficient data for technical analysis' };
        }

        const prices = data.map(item => item.close).filter(price => price !== null);
        const volumes = data.map(item => item.volume).filter(vol => vol !== null);

        return {
            movingAverages: {
                sma20: this.calculateSMA(prices, 20),
                sma50: this.calculateSMA(prices, 50),
                ema12: this.calculateEMA(prices, 12),
                ema26: this.calculateEMA(prices, 26)
            },
            oscillators: {
                rsi: this.calculateRSI(prices, 14),
                macd: this.calculateMACD(prices)
            },
            volatility: {
                bollingerBands: this.calculateBollingerBands(prices, 20),
                standardDeviation: this.calculateStandardDeviation(prices)
            },
            volume: {
                averageVolume: volumes.reduce((a, b) => a + b, 0) / volumes.length,
                volumeTrend: this.calculateVolumeTrend(volumes),
                volumeRatio: volumes.slice(-5).reduce((a, b) => a + b, 0) / (volumes.slice(-10, -5).reduce((a, b) => a + b, 0) || 1)
            },
            signals: this.generateTradingSignals(prices, volumes)
        };
    }

    calculateSMA(prices, period) {
        if (prices.length < period) return null;
        const recent = prices.slice(-period);
        return recent.reduce((a, b) => a + b, 0) / period;
    }

    calculateEMA(prices, period) {
        if (prices.length < period) return null;

        const k = 2 / (period + 1);
        let ema = prices.slice(0, period).reduce((a, b) => a + b, 0) / period;

        for (let i = period; i < prices.length; i++) {
            ema = (prices[i] * k) + (ema * (1 - k));
        }

        return ema;
    }

    calculateRSI(prices, period = 14) {
        if (prices.length < period + 1) return null;

        const gains = [];
        const losses = [];

        for (let i = 1; i < prices.length; i++) {
            const change = prices[i] - prices[i - 1];
            gains.push(change > 0 ? change : 0);
            losses.push(change < 0 ? Math.abs(change) : 0);
        }

        const avgGain = gains.slice(-period).reduce((a, b) => a + b, 0) / period;
        const avgLoss = losses.slice(-period).reduce((a, b) => a + b, 0) / period;

        if (avgLoss === 0) return 100;

        const rs = avgGain / avgLoss;
        return 100 - (100 / (1 + rs));
    }

    calculateMACD(prices, fast = 12, slow = 26, signal = 9) {
        if (prices.length < slow) return null;

        const emaFast = this.calculateEMA(prices, fast);
        const emaSlow = this.calculateEMA(prices, slow);
        const macdLine = emaFast - emaSlow;

        // For simplicity, returning current MACD value
        // Full implementation would calculate signal line and histogram
        return {
            macd: macdLine,
            signal: null, // Would need more complex calculation
            histogram: null
        };
    }

    calculateBollingerBands(prices, period = 20, stdDev = 2) {
        if (prices.length < period) return null;

        const sma = this.calculateSMA(prices, period);
        const recentPrices = prices.slice(-period);

        const variance = recentPrices.reduce((sum, price) => {
            return sum + Math.pow(price - sma, 2);
        }, 0) / period;

        const standardDeviation = Math.sqrt(variance);

        return {
            upper: sma + (standardDeviation * stdDev),
            middle: sma,
            lower: sma - (standardDeviation * stdDev)
        };
    }

    calculateStandardDeviation(prices) {
        const mean = prices.reduce((a, b) => a + b, 0) / prices.length;
        const variance = prices.reduce((sum, price) => sum + Math.pow(price - mean, 2), 0) / prices.length;
        return Math.sqrt(variance);
    }

    calculateVolumeTrend(volumes) {
        if (volumes.length < 2) return 'unknown';

        const recent = volumes.slice(-5);
        const earlier = volumes.slice(-10, -5);

        const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
        const earlierAvg = earlier.reduce((a, b) => a + b, 0) / earlier.length;

        if (recentAvg > earlierAvg * 1.1) return 'increasing';
        if (recentAvg < earlierAvg * 0.9) return 'decreasing';
        return 'stable';
    }

    generateTradingSignals(prices, volumes) {
        const signals = [];
        const currentPrice = prices[prices.length - 1];
        const sma20 = this.calculateSMA(prices, 20);
        const sma50 = this.calculateSMA(prices, 50);
        const rsi = this.calculateRSI(prices);

        // Golden Cross / Death Cross
        if (sma20 && sma50) {
            if (sma20 > sma50 && currentPrice > sma20) {
                signals.push({ type: 'bullish', indicator: 'golden_cross', strength: 'strong' });
            } else if (sma20 < sma50 && currentPrice < sma20) {
                signals.push({ type: 'bearish', indicator: 'death_cross', strength: 'strong' });
            }
        }

        // RSI signals
        if (rsi) {
            if (rsi > 70) {
                signals.push({ type: 'bearish', indicator: 'rsi_overbought', strength: 'medium' });
            } else if (rsi < 30) {
                signals.push({ type: 'bullish', indicator: 'rsi_oversold', strength: 'medium' });
            }
        }

        return signals;
    }

    // Helper methods
    getPeriodStart(period) {
        const now = new Date();
        const periods = {
            '1d': 1,
            '5d': 5,
            '1mo': 30,
            '3mo': 90,
            '6mo': 180,
            '1y': 365,
            '2y': 730,
            '5y': 1825,
            '10y': 3650,
            'ytd': Math.floor((now - new Date(now.getFullYear(), 0, 1)) / (1000 * 60 * 60 * 24)),
            'max': 7300
        };

        const days = periods[period] || 30;
        return Math.floor((now.getTime() - (days * 24 * 60 * 60 * 1000)) / 1000);
    }

    calculateHistoricalSummary(data) {
        if (!data || data.length === 0) return null;

        const prices = data.map(item => item.close).filter(price => price !== null);
        const volumes = data.map(item => item.volume).filter(vol => vol !== null);

        const firstPrice = prices[0];
        const lastPrice = prices[prices.length - 1];

        return {
            totalReturn: ((lastPrice - firstPrice) / firstPrice) * 100,
            volatility: this.calculateStandardDeviation(prices) / (prices.reduce((a, b) => a + b, 0) / prices.length) * 100,
            highestPrice: Math.max(...prices),
            lowestPrice: Math.min(...prices),
            averageVolume: volumes.reduce((a, b) => a + b, 0) / volumes.length,
            tradingDays: data.length
        };
    }

    processFinancialData(statements) {
        return statements.slice(0, 4).map(statement => {
            const processed = {};
            for (const [key, value] of Object.entries(statement)) {
                if (key !== 'endDate' && key !== 'maxAge') {
                    processed[key] = value?.raw || value;
                }
            }
            processed.endDate = new Date(statement.endDate?.raw * 1000 || Date.now()).toISOString().split('T')[0];
            return processed;
        });
    }

    calculateFinancialRatios(financialData) {
        return {
            currentRatio: financialData.currentRatio?.raw || 'N/A',
            debtToEquity: financialData.debtToEquity?.raw || 'N/A',
            returnOnEquity: financialData.returnOnEquity?.raw || 'N/A',
            returnOnAssets: financialData.returnOnAssets?.raw || 'N/A',
            grossMargins: financialData.grossMargins?.raw || 'N/A',
            operatingMargins: financialData.operatingMargins?.raw || 'N/A',
            profitMargins: financialData.profitMargins?.raw || 'N/A'
        };
    }

    processRecommendations(trends) {
        return trends.map(trend => ({
            period: trend.period || 'current',
            strongBuy: trend.strongBuy || 0,
            buy: trend.buy || 0,
            hold: trend.hold || 0,
            sell: trend.sell || 0,
            strongSell: trend.strongSell || 0
        }));
    }

    processUpgradesDowngrades(history) {
        return history.slice(0, 10).map(item => ({
            date: new Date((item.epochGradeDate || 0) * 1000).toISOString().split('T')[0],
            firm: item.firm || 'Unknown',
            fromGrade: item.fromGrade || 'N/A',
            toGrade: item.toGrade || 'N/A',
            action: item.action || 'N/A'
        }));
    }

    summarizeRecommendations(trends) {
        if (!trends || trends.length === 0) return null;

        const latest = trends[0];
        const total = (latest.strongBuy || 0) + (latest.buy || 0) + (latest.hold || 0) + (latest.sell || 0) + (latest.strongSell || 0);

        if (total === 0) return null;

        const bullish = (latest.strongBuy || 0) + (latest.buy || 0);
        const bearish = (latest.sell || 0) + (latest.strongSell || 0);
        const neutral = latest.hold || 0;

        return {
            totalAnalysts: total,
            bullishPercent: (bullish / total) * 100,
            bearishPercent: (bearish / total) * 100,
            neutralPercent: (neutral / total) * 100,
            consensus: bullish > bearish + neutral ? 'Buy' :
                      bearish > bullish + neutral ? 'Sell' : 'Hold'
        };
    }

    generateInvestmentAnalysis(data) {
        const analysis = {
            overallScore: 0,
            factors: [],
            recommendation: 'Hold',
            riskLevel: 'Medium',
            keyMetrics: {},
            strengths: [],
            concerns: []
        };

        // Analyze quote data
        if (data.quote && !data.quote.error) {
            const quote = data.quote;

            if (quote.changePercent > 5) {
                analysis.factors.push('Strong recent performance');
                analysis.overallScore += 10;
            } else if (quote.changePercent < -5) {
                analysis.factors.push('Recent price decline');
                analysis.overallScore -= 10;
            }

            analysis.keyMetrics.currentPrice = quote.price;
            analysis.keyMetrics.dayChange = quote.changePercent;
        }

        // Analyze technical indicators
        if (data.technicalAnalysis && !data.technicalAnalysis.error) {
            const tech = data.technicalAnalysis;

            if (tech.oscillators?.rsi) {
                if (tech.oscillators.rsi < 30) {
                    analysis.strengths.push('Oversold conditions may indicate buying opportunity');
                    analysis.overallScore += 15;
                } else if (tech.oscillators.rsi > 70) {
                    analysis.concerns.push('Overbought conditions suggest possible correction');
                    analysis.overallScore -= 15;
                }
            }

            if (tech.signals && tech.signals.length > 0) {
                const bullishSignals = tech.signals.filter(s => s.type === 'bullish').length;
                const bearishSignals = tech.signals.filter(s => s.type === 'bearish').length;

                analysis.overallScore += (bullishSignals * 10) - (bearishSignals * 10);
            }
        }

        // Determine final recommendation
        if (analysis.overallScore > 20) {
            analysis.recommendation = 'Strong Buy';
            analysis.riskLevel = 'High';
        } else if (analysis.overallScore > 10) {
            analysis.recommendation = 'Buy';
            analysis.riskLevel = 'Medium-High';
        } else if (analysis.overallScore < -20) {
            analysis.recommendation = 'Strong Sell';
            analysis.riskLevel = 'High';
        } else if (analysis.overallScore < -10) {
            analysis.recommendation = 'Sell';
            analysis.riskLevel = 'Medium-High';
        } else {
            analysis.recommendation = 'Hold';
            analysis.riskLevel = 'Medium';
        }

        return analysis;
    }

    // Cache methods
    getFromCache(key) {
        const cached = this.cache.get(key);
        if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
            return cached.data;
        }
        return null;
    }

    setCache(key, data) {
        this.cache.set(key, {
            data: data,
            timestamp: Date.now()
        });

        // Clean old cache entries
        if (this.cache.size > 100) {
            const oldestKey = this.cache.keys().next().value;
            this.cache.delete(oldestKey);
        }
    }
}

module.exports = StockAnalyzerTool;