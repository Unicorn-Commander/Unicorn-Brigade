/**
 * Chart Generator Tool - Data visualization and chart creation
 * UC2 Internal Tool v1.0.0
 */

const fs = require('fs').promises;
const path = require('path');
const crypto = require('crypto');

class ChartGeneratorTool {
    constructor() {
        this.name = 'chartGenerator';
        this.version = '1.0.0';
        this.description = 'Generate professional charts and data visualizations';
        this.category = 'visualization';
        this.permissions = ['basic', 'filesystem'];

        // Chart.js and canvas dependencies will be checked at runtime
        this.dependencies = {
            'chart.js': '^4.4.0',
            'canvas': '^2.11.2',
            'chartjs-node-canvas': '^4.1.6'
        };

        this.schema = {
            type: 'object',
            properties: {
                type: {
                    type: 'string',
                    enum: ['bar', 'line', 'pie', 'doughnut', 'scatter', 'radar', 'polarArea', 'bubble'],
                    description: 'Type of chart to generate'
                },
                data: {
                    type: 'object',
                    description: 'Chart data - can include labels, datasets, etc.',
                    properties: {
                        labels: {
                            type: 'array',
                            items: { type: 'string' },
                            description: 'Chart labels'
                        },
                        datasets: {
                            type: 'array',
                            description: 'Chart datasets',
                            items: {
                                type: 'object',
                                properties: {
                                    label: { type: 'string' },
                                    data: {
                                        type: 'array',
                                        items: { type: 'number' }
                                    },
                                    backgroundColor: {
                                        oneOf: [
                                            { type: 'string' },
                                            { type: 'array', items: { type: 'string' } }
                                        ]
                                    },
                                    borderColor: {
                                        oneOf: [
                                            { type: 'string' },
                                            { type: 'array', items: { type: 'string' } }
                                        ]
                                    },
                                    borderWidth: { type: 'number' }
                                }
                            }
                        }
                    }
                },
                csvData: {
                    type: 'string',
                    description: 'CSV formatted data to convert to chart'
                },
                jsonData: {
                    type: 'object',
                    description: 'JSON data array to convert to chart'
                },
                options: {
                    type: 'object',
                    description: 'Chart.js options for customization',
                    properties: {
                        responsive: { type: 'boolean', default: true },
                        plugins: {
                            type: 'object',
                            properties: {
                                title: {
                                    type: 'object',
                                    properties: {
                                        display: { type: 'boolean' },
                                        text: { type: 'string' }
                                    }
                                },
                                legend: {
                                    type: 'object',
                                    properties: {
                                        display: { type: 'boolean' },
                                        position: {
                                            type: 'string',
                                            enum: ['top', 'left', 'bottom', 'right', 'chartArea']
                                        }
                                    }
                                }
                            }
                        },
                        scales: { type: 'object' }
                    }
                },
                width: {
                    type: 'number',
                    default: 800,
                    minimum: 100,
                    maximum: 4000,
                    description: 'Chart width in pixels'
                },
                height: {
                    type: 'number',
                    default: 600,
                    minimum: 100,
                    maximum: 4000,
                    description: 'Chart height in pixels'
                },
                outputFormat: {
                    type: 'string',
                    enum: ['png', 'jpeg', 'svg', 'html', 'json'],
                    default: 'png',
                    description: 'Output format for the chart'
                },
                outputPath: {
                    type: 'string',
                    description: 'File path to save the chart (optional)'
                },
                theme: {
                    type: 'string',
                    enum: ['default', 'dark', 'light', 'colorful', 'minimal'],
                    default: 'default',
                    description: 'Chart color theme'
                }
            },
            required: ['type']
        };

        // Default color schemes for themes
        this.themes = {
            default: {
                backgroundColor: [
                    'rgba(54, 162, 235, 0.6)',
                    'rgba(255, 99, 132, 0.6)',
                    'rgba(255, 205, 86, 0.6)',
                    'rgba(75, 192, 192, 0.6)',
                    'rgba(153, 102, 255, 0.6)',
                    'rgba(255, 159, 64, 0.6)'
                ],
                borderColor: [
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 99, 132, 1)',
                    'rgba(255, 205, 86, 1)',
                    'rgba(75, 192, 192, 1)',
                    'rgba(153, 102, 255, 1)',
                    'rgba(255, 159, 64, 1)'
                ]
            },
            dark: {
                backgroundColor: [
                    'rgba(99, 102, 241, 0.6)',
                    'rgba(236, 72, 153, 0.6)',
                    'rgba(245, 158, 11, 0.6)',
                    'rgba(16, 185, 129, 0.6)',
                    'rgba(139, 92, 246, 0.6)',
                    'rgba(249, 115, 22, 0.6)'
                ],
                borderColor: [
                    'rgba(99, 102, 241, 1)',
                    'rgba(236, 72, 153, 1)',
                    'rgba(245, 158, 11, 1)',
                    'rgba(16, 185, 129, 1)',
                    'rgba(139, 92, 246, 1)',
                    'rgba(249, 115, 22, 1)'
                ]
            },
            light: {
                backgroundColor: [
                    'rgba(191, 219, 254, 0.8)',
                    'rgba(252, 165, 165, 0.8)',
                    'rgba(254, 240, 138, 0.8)',
                    'rgba(167, 243, 208, 0.8)',
                    'rgba(196, 181, 253, 0.8)',
                    'rgba(253, 186, 116, 0.8)'
                ],
                borderColor: [
                    'rgba(59, 130, 246, 1)',
                    'rgba(239, 68, 68, 1)',
                    'rgba(245, 158, 11, 1)',
                    'rgba(34, 197, 94, 1)',
                    'rgba(147, 51, 234, 1)',
                    'rgba(249, 115, 22, 1)'
                ]
            },
            colorful: {
                backgroundColor: [
                    'rgba(255, 0, 128, 0.6)',
                    'rgba(0, 255, 128, 0.6)',
                    'rgba(128, 0, 255, 0.6)',
                    'rgba(255, 128, 0, 0.6)',
                    'rgba(0, 128, 255, 0.6)',
                    'rgba(255, 255, 0, 0.6)'
                ],
                borderColor: [
                    'rgba(255, 0, 128, 1)',
                    'rgba(0, 255, 128, 1)',
                    'rgba(128, 0, 255, 1)',
                    'rgba(255, 128, 0, 1)',
                    'rgba(0, 128, 255, 1)',
                    'rgba(255, 255, 0, 1)'
                ]
            },
            minimal: {
                backgroundColor: [
                    'rgba(107, 114, 128, 0.6)',
                    'rgba(156, 163, 175, 0.6)',
                    'rgba(209, 213, 219, 0.6)',
                    'rgba(75, 85, 99, 0.6)',
                    'rgba(55, 65, 81, 0.6)',
                    'rgba(31, 41, 55, 0.6)'
                ],
                borderColor: [
                    'rgba(107, 114, 128, 1)',
                    'rgba(156, 163, 175, 1)',
                    'rgba(209, 213, 219, 1)',
                    'rgba(75, 85, 99, 1)',
                    'rgba(55, 65, 81, 1)',
                    'rgba(31, 41, 55, 1)'
                ]
            }
        };
    }

    /**
     * Execute chart generation
     */
    async execute(params, context = {}) {
        try {
            const {
                type,
                data,
                csvData,
                jsonData,
                options = {},
                width = 800,
                height = 600,
                outputFormat = 'png',
                outputPath,
                theme = 'default'
            } = params;

            // Input validation
            if (!type) {
                throw new Error('Chart type is required');
            }

            const startTime = process.hrtime.bigint();

            // Process data from different sources
            let processedData = await this._processData(data, csvData, jsonData, type, theme);

            // Generate chart configuration
            const chartConfig = this._buildChartConfig(type, processedData, options, theme);

            // Generate chart based on output format
            let result;
            if (outputFormat === 'json') {
                result = await this._generateConfigOutput(chartConfig, outputPath);
            } else if (outputFormat === 'html') {
                result = await this._generateHTMLOutput(chartConfig, width, height, outputPath);
            } else if (outputFormat === 'svg') {
                result = await this._generateSVGOutput(chartConfig, width, height, outputPath);
            } else {
                // PNG/JPEG - requires canvas
                result = await this._generateImageOutput(chartConfig, width, height, outputFormat, outputPath);
            }

            const executionTime = Number(process.hrtime.bigint() - startTime) / 1000000;

            return {
                success: true,
                chartType: type,
                outputFormat: outputFormat,
                dimensions: { width, height },
                theme: theme,
                result: result,
                executionTime: `${executionTime.toFixed(2)}ms`,
                timestamp: new Date().toISOString()
            };

        } catch (error) {
            return {
                success: false,
                error: error.message,
                chartType: params.type,
                timestamp: new Date().toISOString()
            };
        }
    }

    /**
     * Process data from various input formats
     * @private
     */
    async _processData(data, csvData, jsonData, chartType, theme) {
        let processedData = data;

        // Process CSV data
        if (csvData && !data) {
            processedData = this._parseCSVData(csvData, chartType);
        }

        // Process JSON data
        if (jsonData && !data && !csvData) {
            processedData = this._parseJSONData(jsonData, chartType);
        }

        // Apply theme colors if not specified
        if (processedData && processedData.datasets) {
            processedData.datasets = processedData.datasets.map((dataset, index) => {
                if (!dataset.backgroundColor || !dataset.borderColor) {
                    const colors = this.themes[theme] || this.themes.default;
                    return {
                        ...dataset,
                        backgroundColor: dataset.backgroundColor || colors.backgroundColor[index % colors.backgroundColor.length],
                        borderColor: dataset.borderColor || colors.borderColor[index % colors.borderColor.length],
                        borderWidth: dataset.borderWidth || 2
                    };
                }
                return dataset;
            });
        }

        // Generate sample data if none provided
        if (!processedData) {
            processedData = this._generateSampleData(chartType, theme);
        }

        return processedData;
    }

    /**
     * Parse CSV data to chart format
     * @private
     */
    _parseCSVData(csvData, chartType) {
        const lines = csvData.trim().split('\n');
        if (lines.length < 2) {
            throw new Error('CSV data must have at least a header row and one data row');
        }

        const headers = lines[0].split(',').map(h => h.trim());
        const labels = [];
        const dataPoints = [];

        // Parse data rows
        for (let i = 1; i < lines.length; i++) {
            const values = lines[i].split(',').map(v => v.trim());
            if (values.length >= 2) {
                labels.push(values[0]);
                dataPoints.push(parseFloat(values[1]) || 0);
            }
        }

        return {
            labels: labels,
            datasets: [{
                label: headers[1] || 'Data',
                data: dataPoints
            }]
        };
    }

    /**
     * Parse JSON data to chart format
     * @private
     */
    _parseJSONData(jsonData, chartType) {
        if (Array.isArray(jsonData)) {
            // Assume array of objects with consistent keys
            const firstItem = jsonData[0];
            if (!firstItem || typeof firstItem !== 'object') {
                throw new Error('JSON data array must contain objects');
            }

            const keys = Object.keys(firstItem);
            const labelKey = keys[0];
            const dataKey = keys[1] || keys[0];

            const labels = jsonData.map(item => String(item[labelKey]));
            const dataPoints = jsonData.map(item => parseFloat(item[dataKey]) || 0);

            return {
                labels: labels,
                datasets: [{
                    label: dataKey,
                    data: dataPoints
                }]
            };
        } else if (jsonData && typeof jsonData === 'object') {
            // Direct chart data format
            return jsonData;
        } else {
            throw new Error('JSON data must be an array of objects or chart data object');
        }
    }

    /**
     * Generate sample data for demonstration
     * @private
     */
    _generateSampleData(chartType, theme) {
        const sampleData = {
            bar: {
                labels: ['January', 'February', 'March', 'April', 'May', 'June'],
                datasets: [{
                    label: 'Sample Data',
                    data: [12, 19, 3, 5, 2, 3]
                }]
            },
            line: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                datasets: [{
                    label: 'Sample Trend',
                    data: [10, 15, 12, 20, 25, 22],
                    fill: false,
                    tension: 0.4
                }]
            },
            pie: {
                labels: ['Red', 'Blue', 'Yellow', 'Green', 'Purple', 'Orange'],
                datasets: [{
                    data: [12, 19, 3, 5, 2, 3]
                }]
            },
            doughnut: {
                labels: ['Desktop', 'Mobile', 'Tablet'],
                datasets: [{
                    data: [55, 35, 10]
                }]
            },
            scatter: {
                datasets: [{
                    label: 'Sample Points',
                    data: [
                        { x: 10, y: 20 },
                        { x: 15, y: 25 },
                        { x: 20, y: 15 },
                        { x: 25, y: 30 },
                        { x: 30, y: 35 }
                    ]
                }]
            },
            radar: {
                labels: ['Speed', 'Reliability', 'Comfort', 'Safety', 'Efficiency'],
                datasets: [{
                    label: 'Product A',
                    data: [80, 90, 70, 85, 75]
                }]
            }
        };

        return sampleData[chartType] || sampleData.bar;
    }

    /**
     * Build Chart.js configuration
     * @private
     */
    _buildChartConfig(type, data, userOptions, theme) {
        const defaultOptions = {
            responsive: true,
            plugins: {
                title: {
                    display: false
                },
                legend: {
                    display: true,
                    position: 'top'
                }
            }
        };

        // Merge user options with defaults
        const options = this._deepMerge(defaultOptions, userOptions);

        return {
            type: type,
            data: data,
            options: options
        };
    }

    /**
     * Generate JSON config output
     * @private
     */
    async _generateConfigOutput(chartConfig, outputPath) {
        const configJson = JSON.stringify(chartConfig, null, 2);

        if (outputPath) {
            await this._saveToFile(configJson, outputPath);
            return {
                type: 'json',
                path: outputPath,
                size: configJson.length,
                config: chartConfig
            };
        }

        return {
            type: 'json',
            config: chartConfig,
            configString: configJson
        };
    }

    /**
     * Generate HTML output with Chart.js
     * @private
     */
    async _generateHTMLOutput(chartConfig, width, height, outputPath) {
        const chartId = `chart_${crypto.randomBytes(8).toString('hex')}`;

        const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chart Visualization</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .chart-container {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 20px;
            margin: 0 auto;
            max-width: ${width + 40}px;
        }
        canvas {
            max-width: 100%;
            height: auto;
        }
    </style>
</head>
<body>
    <div class="chart-container">
        <canvas id="${chartId}" width="${width}" height="${height}"></canvas>
    </div>
    <script>
        const ctx = document.getElementById('${chartId}').getContext('2d');
        const chart = new Chart(ctx, ${JSON.stringify(chartConfig, null, 2)});
    </script>
</body>
</html>`;

        if (outputPath) {
            await this._saveToFile(html, outputPath);
            return {
                type: 'html',
                path: outputPath,
                size: html.length,
                chartId: chartId
            };
        }

        return {
            type: 'html',
            html: html,
            chartId: chartId
        };
    }

    /**
     * Generate SVG output (simplified version)
     * @private
     */
    async _generateSVGOutput(chartConfig, width, height, outputPath) {
        // This is a simplified SVG generator for basic charts
        // For production use, consider using Chart.js with svg2 adapter

        const svg = this._generateBasicSVG(chartConfig, width, height);

        if (outputPath) {
            await this._saveToFile(svg, outputPath);
            return {
                type: 'svg',
                path: outputPath,
                size: svg.length
            };
        }

        return {
            type: 'svg',
            svg: svg
        };
    }

    /**
     * Generate image output using canvas
     * @private
     */
    async _generateImageOutput(chartConfig, width, height, format, outputPath) {
        try {
            // Try to load chartjs-node-canvas for server-side rendering
            const { ChartJSNodeCanvas } = require('chartjs-node-canvas');

            const chartJSNodeCanvas = new ChartJSNodeCanvas({
                width: width,
                height: height,
                backgroundColour: 'white'
            });

            const buffer = await chartJSNodeCanvas.renderToBuffer(chartConfig, format);

            if (outputPath) {
                await fs.writeFile(outputPath, buffer);
                return {
                    type: format,
                    path: outputPath,
                    size: buffer.length,
                    dimensions: { width, height }
                };
            }

            return {
                type: format,
                buffer: buffer,
                base64: buffer.toString('base64'),
                dimensions: { width, height }
            };

        } catch (error) {
            // Fallback: return HTML with instructions to screenshot
            const htmlOutput = await this._generateHTMLOutput(chartConfig, width, height, null);

            return {
                type: 'html_fallback',
                message: 'Canvas libraries not available. Generated HTML instead.',
                html: htmlOutput.html,
                instructions: 'Open this HTML in a browser to view the chart, or install chartjs-node-canvas for direct image generation.',
                fallbackReason: error.message
            };
        }
    }

    /**
     * Generate basic SVG for simple charts
     * @private
     */
    _generateBasicSVG(chartConfig, width, height) {
        const { type, data } = chartConfig;

        // Simple bar chart SVG generation
        if (type === 'bar' && data.datasets && data.datasets[0]) {
            return this._generateBarChartSVG(data, width, height);
        }

        // Fallback SVG
        return `
<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
    <rect width="100%" height="100%" fill="white"/>
    <text x="50%" y="50%" text-anchor="middle" fill="black" font-family="Arial" font-size="16">
        Chart Type: ${type}
    </text>
    <text x="50%" y="60%" text-anchor="middle" fill="gray" font-family="Arial" font-size="12">
        SVG generation for ${type} charts not yet implemented
    </text>
</svg>`;
    }

    /**
     * Generate bar chart SVG
     * @private
     */
    _generateBarChartSVG(data, width, height) {
        const padding = 60;
        const chartWidth = width - padding * 2;
        const chartHeight = height - padding * 2;

        const values = data.datasets[0].data;
        const labels = data.labels || values.map((_, i) => `Item ${i + 1}`);
        const maxValue = Math.max(...values);

        const barWidth = chartWidth / values.length * 0.8;
        const barSpacing = chartWidth / values.length * 0.2;

        let svg = `<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">`;
        svg += `<rect width="100%" height="100%" fill="white"/>`;

        // Draw bars
        values.forEach((value, index) => {
            const barHeight = (value / maxValue) * chartHeight;
            const x = padding + (index * (barWidth + barSpacing));
            const y = height - padding - barHeight;

            svg += `<rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}"
                    fill="rgba(54, 162, 235, 0.6)" stroke="rgba(54, 162, 235, 1)" stroke-width="2"/>`;

            // Add label
            svg += `<text x="${x + barWidth/2}" y="${height - padding + 20}"
                    text-anchor="middle" fill="black" font-family="Arial" font-size="12">${labels[index]}</text>`;

            // Add value
            svg += `<text x="${x + barWidth/2}" y="${y - 5}"
                    text-anchor="middle" fill="black" font-family="Arial" font-size="10">${value}</text>`;
        });

        svg += `</svg>`;
        return svg;
    }

    /**
     * Save content to file
     * @private
     */
    async _saveToFile(content, filePath) {
        const dir = path.dirname(filePath);
        await fs.mkdir(dir, { recursive: true });

        if (Buffer.isBuffer(content)) {
            await fs.writeFile(filePath, content);
        } else {
            await fs.writeFile(filePath, content, 'utf8');
        }
    }

    /**
     * Deep merge objects
     * @private
     */
    _deepMerge(target, source) {
        const result = { ...target };

        for (const key in source) {
            if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
                result[key] = this._deepMerge(result[key] || {}, source[key]);
            } else {
                result[key] = source[key];
            }
        }

        return result;
    }

    /**
     * Get tool information
     */
    getInfo() {
        return {
            name: this.name,
            version: this.version,
            description: this.description,
            category: this.category,
            permissions: this.permissions,
            schema: this.schema,
            dependencies: this.dependencies,
            supportedChartTypes: ['bar', 'line', 'pie', 'doughnut', 'scatter', 'radar', 'polarArea', 'bubble'],
            supportedFormats: ['png', 'jpeg', 'svg', 'html', 'json'],
            supportedThemes: Object.keys(this.themes),
            examples: [
                {
                    description: 'Simple bar chart',
                    input: {
                        type: 'bar',
                        data: {
                            labels: ['A', 'B', 'C'],
                            datasets: [{ label: 'Values', data: [10, 20, 30] }]
                        }
                    },
                    output: { chartType: 'bar', outputFormat: 'png' }
                },
                {
                    description: 'CSV to pie chart',
                    input: {
                        type: 'pie',
                        csvData: 'Category,Value\nApples,30\nBananas,20\nOranges,50',
                        theme: 'colorful'
                    },
                    output: { chartType: 'pie', theme: 'colorful' }
                },
                {
                    description: 'Line chart with custom options',
                    input: {
                        type: 'line',
                        jsonData: [
                            { month: 'Jan', sales: 1000 },
                            { month: 'Feb', sales: 1500 },
                            { month: 'Mar', sales: 1200 }
                        ],
                        options: {
                            plugins: {
                                title: { display: true, text: 'Monthly Sales' }
                            }
                        },
                        outputFormat: 'html'
                    },
                    output: { chartType: 'line', outputFormat: 'html' }
                }
            ]
        };
    }

    /**
     * Validate tool configuration
     */
    validate() {
        const issues = [];

        // Check if Chart.js dependencies are available (optional for basic functionality)
        try {
            require.resolve('chart.js');
        } catch (error) {
            issues.push('Chart.js not installed - image generation will be limited');
        }

        try {
            require.resolve('chartjs-node-canvas');
        } catch (error) {
            issues.push('chartjs-node-canvas not installed - PNG/JPEG generation will fall back to HTML');
        }

        return {
            valid: true, // Tool can work with basic functionality even without all dependencies
            issues: issues,
            capabilities: {
                htmlGeneration: true,
                jsonGeneration: true,
                basicSvgGeneration: true,
                imageGeneration: issues.length === 0
            }
        };
    }
}

// Export for CommonJS and ES6
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChartGeneratorTool;
} else if (typeof exports !== 'undefined') {
    exports.ChartGeneratorTool = ChartGeneratorTool;
}

// Also export as default for ES6 import
if (typeof window === 'undefined') {
    module.exports.default = ChartGeneratorTool;
}