const NodeCache = require('node-cache');

class ChartBuilder {
    constructor() {
        this.cache = new NodeCache({ stdTTL: 1800 }); // 30 minute cache

        this.chartTypes = {
            'bar': {
                description: 'Vertical or horizontal bar charts',
                variants: ['vertical', 'horizontal', 'stacked', 'grouped'],
                best_for: ['categorical data', 'comparisons'],
                data_requirements: ['categories', 'values']
            },
            'line': {
                description: 'Line charts for trends over time',
                variants: ['single', 'multi-series', 'area', 'step'],
                best_for: ['time series', 'trends', 'continuous data'],
                data_requirements: ['x-axis values', 'y-axis values']
            },
            'pie': {
                description: 'Pie and doughnut charts for proportions',
                variants: ['pie', 'doughnut', 'semi-circle'],
                best_for: ['proportions', 'parts of whole'],
                data_requirements: ['categories', 'values']
            },
            'scatter': {
                description: 'Scatter plots for correlation analysis',
                variants: ['basic', 'bubble', 'regression'],
                best_for: ['correlation', 'distribution', 'outlier detection'],
                data_requirements: ['x-values', 'y-values', 'optional size/color']
            },
            'heatmap': {
                description: 'Heat maps for matrix data visualization',
                variants: ['basic', 'clustered', 'calendar'],
                best_for: ['matrix data', 'correlation matrices', 'density'],
                data_requirements: ['x-axis categories', 'y-axis categories', 'intensity values']
            },
            'radar': {
                description: 'Radar/spider charts for multivariate data',
                variants: ['filled', 'line', 'multi-series'],
                best_for: ['performance metrics', 'skill assessment', 'multivariate comparison'],
                data_requirements: ['dimensions', 'values for each dimension']
            },
            'treemap': {
                description: 'Treemap for hierarchical data',
                variants: ['basic', 'nested', 'sunburst'],
                best_for: ['hierarchical data', 'file sizes', 'market share'],
                data_requirements: ['hierarchical structure', 'size values']
            },
            'waterfall': {
                description: 'Waterfall charts for cumulative analysis',
                variants: ['basic', 'bridge', 'variance'],
                best_for: ['financial analysis', 'change analysis', 'cumulative effects'],
                data_requirements: ['categories', 'positive/negative values']
            }
        };

        this.colorPalettes = {
            'default': ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e', '#95a5a6'],
            'pastel': ['#fbb4ae', '#b3cde3', '#ccebc5', '#decbe4', '#fed9a6', '#ffffcc', '#e5d8bd', '#fddaec'],
            'vibrant': ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#feca57', '#ff9ff3', '#54a0ff', '#5f27cd'],
            'corporate': ['#2c3e50', '#3498db', '#e74c3c', '#f39c12', '#27ae60', '#8e44ad', '#16a085', '#d35400'],
            'monochrome': ['#2d3436', '#636e72', '#74b9ff', '#0984e3', '#00b894', '#00cec9', '#6c5ce7', '#fdcb6e'],
            'gradient': ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe', '#43e97b', '#38f9d7']
        };

        this.exportFormats = ['png', 'jpg', 'svg', 'pdf', 'html', 'json'];

        this.themes = {
            'light': {
                background: '#ffffff',
                text: '#2c3e50',
                grid: '#ecf0f1',
                accent: '#3498db'
            },
            'dark': {
                background: '#2c3e50',
                text: '#ecf0f1',
                grid: '#34495e',
                accent: '#3498db'
            },
            'minimal': {
                background: '#fafafa',
                text: '#333333',
                grid: '#e0e0e0',
                accent: '#666666'
            }
        };

        this.animationTypes = [
            'none', 'fade', 'slide', 'bounce', 'elastic', 'grow'
        ];
    }

    async buildChart(data, options = {}) {
        try {
            const config = {
                type: options.type || 'bar',
                title: options.title || '',
                subtitle: options.subtitle || '',
                width: options.width || 800,
                height: options.height || 600,
                theme: options.theme || 'light',
                colorPalette: options.colorPalette || 'default',
                showLegend: options.showLegend !== false,
                showGrid: options.showGrid !== false,
                showAxes: options.showAxes !== false,
                interactive: options.interactive !== false,
                animation: options.animation || 'fade',
                responsive: options.responsive !== false,
                xAxisLabel: options.xAxisLabel || '',
                yAxisLabel: options.yAxisLabel || '',
                showTooltips: options.showTooltips !== false,
                dataLabels: options.dataLabels || false
            };

            // Validate chart type
            if (!this.chartTypes[config.type]) {
                throw new Error(`Unsupported chart type: ${config.type}`);
            }

            // Process and validate data
            const processedData = this.processChartData(data, config);

            if (!this.validateDataForChartType(processedData, config.type)) {
                throw new Error(`Data format not suitable for ${config.type} chart`);
            }

            // Generate chart configuration
            const chartConfig = this.generateChartConfig(processedData, config);

            // Create chart visualization
            const visualization = this.generateChartVisualization(chartConfig, processedData, config);

            // Generate chart code
            const chartCode = this.generateChartCode(chartConfig, config);

            // Calculate chart statistics
            const statistics = this.calculateChartStatistics(processedData, config);

            const result = {
                chart_metadata: {
                    type: config.type,
                    title: config.title,
                    dimensions: { width: config.width, height: config.height },
                    theme: config.theme,
                    data_points: this.countDataPoints(processedData),
                    interactive: config.interactive,
                    responsive: config.responsive
                },
                chart_configuration: chartConfig,
                visualization: {
                    html: visualization.html,
                    css: visualization.css,
                    javascript: chartCode.javascript,
                    svg: visualization.svg,
                    canvas: visualization.canvas
                },
                data_analysis: {
                    processed_data: processedData,
                    statistics: statistics,
                    data_insights: this.generateDataInsights(processedData, config.type),
                    recommendations: this.generateChartRecommendations(processedData, config)
                },
                customization_options: {
                    available_themes: Object.keys(this.themes),
                    color_palettes: Object.keys(this.colorPalettes),
                    animation_types: this.animationTypes,
                    export_formats: this.exportFormats
                },
                performance_metrics: {
                    estimated_render_time: this.estimateRenderTime(processedData, config),
                    memory_usage: this.estimateMemoryUsage(processedData),
                    optimization_suggestions: this.getOptimizationSuggestions(processedData, config)
                },
                generated_at: new Date().toISOString()
            };

            return result;

        } catch (error) {
            return {
                error: 'Chart building failed',
                message: error.message,
                chart_type: options.type,
                data_provided: Array.isArray(data) ? data.length : typeof data,
                generated_at: new Date().toISOString()
            };
        }
    }

    async createMultiChart(datasets, options = {}) {
        try {
            const config = {
                layout: options.layout || 'grid', // grid, tabs, overlay
                synchronizeAxes: options.synchronizeAxes || false,
                sharedLegend: options.sharedLegend || false,
                spacing: options.spacing || 20,
                ...options
            };

            if (!Array.isArray(datasets) || datasets.length === 0) {
                throw new Error('Datasets must be a non-empty array');
            }

            const charts = [];
            const combinedStatistics = {
                total_charts: datasets.length,
                total_data_points: 0,
                chart_types: [],
                themes_used: []
            };

            // Generate individual charts
            for (let i = 0; i < datasets.length; i++) {
                const dataset = datasets[i];
                const chartOptions = {
                    ...config,
                    ...dataset.options,
                    title: dataset.title || `Chart ${i + 1}`
                };

                const chart = await this.buildChart(dataset.data, chartOptions);

                if (chart.error) {
                    return {
                        error: 'Multi-chart creation failed',
                        message: `Chart ${i + 1}: ${chart.message}`,
                        chart_index: i,
                        generated_at: new Date().toISOString()
                    };
                }

                charts.push(chart);
                combinedStatistics.total_data_points += chart.chart_metadata.data_points;
                combinedStatistics.chart_types.push(chart.chart_metadata.type);
                combinedStatistics.themes_used.push(chart.chart_metadata.theme);
            }

            // Create multi-chart layout
            const layout = this.createMultiChartLayout(charts, config);

            const result = {
                multi_chart_metadata: {
                    layout_type: config.layout,
                    chart_count: datasets.length,
                    synchronized_axes: config.synchronizeAxes,
                    shared_legend: config.sharedLegend,
                    total_dimensions: layout.dimensions
                },
                charts: charts,
                layout: layout,
                combined_statistics: combinedStatistics,
                visualization: {
                    html: layout.html,
                    css: layout.css,
                    javascript: layout.javascript
                },
                export_options: {
                    available_formats: this.exportFormats,
                    recommended_format: 'html',
                    estimated_file_sizes: this.estimateMultiChartFileSizes(charts)
                },
                generated_at: new Date().toISOString()
            };

            return result;

        } catch (error) {
            return {
                error: 'Multi-chart creation failed',
                message: error.message,
                datasets_provided: Array.isArray(datasets) ? datasets.length : 'unknown',
                generated_at: new Date().toISOString()
            };
        }
    }

    async generateDashboard(widgets, options = {}) {
        try {
            const config = {
                layout: options.layout || 'responsive',
                gridColumns: options.gridColumns || 3,
                autoRefresh: options.autoRefresh || false,
                refreshInterval: options.refreshInterval || 30000,
                title: options.title || 'Dashboard',
                showTimestamp: options.showTimestamp !== false,
                ...options
            };

            const dashboardWidgets = [];

            for (const widget of widgets) {
                let processedWidget;

                if (widget.type === 'chart') {
                    processedWidget = await this.buildChart(widget.data, widget.options);
                } else if (widget.type === 'metric') {
                    processedWidget = this.createMetricWidget(widget);
                } else if (widget.type === 'text') {
                    processedWidget = this.createTextWidget(widget);
                } else if (widget.type === 'table') {
                    processedWidget = this.createTableWidget(widget);
                } else {
                    throw new Error(`Unsupported widget type: ${widget.type}`);
                }

                dashboardWidgets.push({
                    id: widget.id || `widget_${dashboardWidgets.length}`,
                    type: widget.type,
                    position: widget.position || { row: 0, col: 0, width: 1, height: 1 },
                    widget: processedWidget
                });
            }

            // Create dashboard layout
            const dashboardLayout = this.createDashboardLayout(dashboardWidgets, config);

            const result = {
                dashboard_metadata: {
                    title: config.title,
                    layout: config.layout,
                    widget_count: dashboardWidgets.length,
                    auto_refresh: config.autoRefresh,
                    refresh_interval: config.refreshInterval,
                    grid_columns: config.gridColumns
                },
                widgets: dashboardWidgets,
                layout: dashboardLayout,
                visualization: {
                    html: dashboardLayout.html,
                    css: dashboardLayout.css,
                    javascript: dashboardLayout.javascript
                },
                interactivity: {
                    filters: this.generateDashboardFilters(dashboardWidgets),
                    drill_downs: this.generateDrillDowns(dashboardWidgets),
                    cross_filtering: this.supportsCrossFiltering(dashboardWidgets)
                },
                generated_at: new Date().toISOString()
            };

            return result;

        } catch (error) {
            return {
                error: 'Dashboard generation failed',
                message: error.message,
                widgets_provided: Array.isArray(widgets) ? widgets.length : 'unknown',
                generated_at: new Date().toISOString()
            };
        }
    }

    processChartData(data, config) {
        if (!data || (Array.isArray(data) && data.length === 0)) {
            throw new Error('No data provided for chart');
        }

        let processed = data;

        // Handle different data formats
        if (Array.isArray(data)) {
            if (data.length > 0 && typeof data[0] === 'object') {
                // Array of objects
                processed = this.processObjectArrayData(data, config);
            } else {
                // Simple array
                processed = this.processSimpleArrayData(data, config);
            }
        } else if (typeof data === 'object') {
            // Object with named properties
            processed = this.processObjectData(data, config);
        }

        // Apply data transformations based on chart type
        processed = this.applyChartSpecificTransformations(processed, config);

        return processed;
    }

    validateDataForChartType(data, chartType) {
        const requirements = this.chartTypes[chartType].data_requirements;

        switch (chartType) {
            case 'bar':
            case 'pie':
                return data.labels && data.values && data.labels.length === data.values.length;

            case 'line':
            case 'scatter':
                return data.x && data.y && data.x.length === data.y.length;

            case 'heatmap':
                return data.x && data.y && data.z && Array.isArray(data.z[0]);

            case 'radar':
                return data.dimensions && data.values && Array.isArray(data.values[0]);

            default:
                return true;
        }
    }

    generateChartConfig(data, config) {
        const theme = this.themes[config.theme];
        const colors = this.colorPalettes[config.colorPalette];

        const chartConfig = {
            type: config.type,
            data: data,
            options: {
                responsive: config.responsive,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: config.showLegend,
                        position: 'top'
                    },
                    tooltip: {
                        enabled: config.showTooltips
                    },
                    title: {
                        display: config.title !== '',
                        text: config.title
                    }
                },
                scales: this.generateScaleConfig(config, theme),
                animation: this.generateAnimationConfig(config.animation),
                elements: {
                    point: {
                        radius: config.type === 'scatter' ? 5 : 3
                    },
                    line: {
                        tension: 0.1
                    }
                }
            },
            theme: theme,
            colors: colors
        };

        return chartConfig;
    }

    generateChartVisualization(chartConfig, data, config) {
        const html = this.generateChartHTML(chartConfig, config);
        const css = this.generateChartCSS(chartConfig, config);
        const svg = this.generateChartSVG(chartConfig, data, config);
        const canvas = this.generateChartCanvas(chartConfig, config);

        return { html, css, svg, canvas };
    }

    generateChartHTML(chartConfig, config) {
        return `
<!DOCTYPE html>
<html>
<head>
    <title>${config.title}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        ${this.generateChartCSS(chartConfig, config)}
    </style>
</head>
<body>
    <div class="chart-container">
        ${config.title ? `<h2 class="chart-title">${config.title}</h2>` : ''}
        ${config.subtitle ? `<h3 class="chart-subtitle">${config.subtitle}</h3>` : ''}
        <div class="chart-wrapper">
            <canvas id="chartCanvas" width="${config.width}" height="${config.height}"></canvas>
        </div>
    </div>
    <script>
        ${this.generateChartCode(chartConfig, config).javascript}
    </script>
</body>
</html>`;
    }

    generateChartCSS(chartConfig, config) {
        const theme = chartConfig.theme;

        return `
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: ${theme.background};
            color: ${theme.text};
            margin: 0;
            padding: 20px;
        }

        .chart-container {
            max-width: ${config.width + 100}px;
            margin: 0 auto;
            background: ${theme.background};
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 20px;
        }

        .chart-title {
            text-align: center;
            color: ${theme.text};
            margin-bottom: 10px;
            font-size: 24px;
            font-weight: bold;
        }

        .chart-subtitle {
            text-align: center;
            color: ${theme.text};
            opacity: 0.8;
            margin-bottom: 20px;
            font-size: 16px;
            font-weight: normal;
        }

        .chart-wrapper {
            position: relative;
            width: 100%;
            height: ${config.height}px;
            margin: 0 auto;
        }

        #chartCanvas {
            max-width: 100%;
            height: auto !important;
        }

        @media (max-width: 768px) {
            .chart-container {
                padding: 10px;
                margin: 10px;
            }

            .chart-title {
                font-size: 20px;
            }

            .chart-subtitle {
                font-size: 14px;
            }
        }`;
    }

    generateChartCode(chartConfig, config) {
        const javascript = `
        document.addEventListener('DOMContentLoaded', function() {
            const ctx = document.getElementById('chartCanvas').getContext('2d');

            const chartData = ${JSON.stringify(chartConfig.data, null, 2)};
            const chartOptions = ${JSON.stringify(chartConfig.options, null, 2)};

            const chart = new Chart(ctx, {
                type: '${chartConfig.type}',
                data: chartData,
                options: chartOptions
            });

            // Add interactivity
            if (${config.interactive}) {
                ctx.canvas.addEventListener('click', function(event) {
                    const points = chart.getElementsAtEventForMode(event, 'nearest', { intersect: true }, true);
                    if (points.length) {
                        const firstPoint = points[0];
                        const label = chart.data.labels[firstPoint.index];
                        const value = chart.data.datasets[firstPoint.datasetIndex].data[firstPoint.index];
                        console.log('Chart clicked:', { label, value });
                    }
                });
            }

            // Auto-refresh for real-time data
            ${config.autoRefresh ? `
            setInterval(function() {
                // Simulate data update
                chart.update();
            }, ${config.refreshInterval || 30000});` : ''}
        });`;

        return { javascript };
    }

    processObjectArrayData(data, config) {
        // Convert array of objects to chart-friendly format
        const keys = Object.keys(data[0]);
        const labels = data.map((item, index) => item[keys[0]] || `Item ${index + 1}`);
        const datasets = keys.slice(1).map(key => ({
            label: key,
            data: data.map(item => item[key] || 0),
            backgroundColor: this.colorPalettes[config.colorPalette] || this.colorPalettes.default
        }));

        return {
            labels: labels,
            datasets: datasets,
            raw: data
        };
    }

    calculateChartStatistics(data, config) {
        const stats = {
            data_points: this.countDataPoints(data),
            chart_type: config.type,
            dimensions: { width: config.width, height: config.height }
        };

        if (data.datasets) {
            stats.datasets = data.datasets.length;
            stats.series_statistics = data.datasets.map(dataset => ({
                label: dataset.label,
                data_points: dataset.data.length,
                min: Math.min(...dataset.data.filter(v => typeof v === 'number')),
                max: Math.max(...dataset.data.filter(v => typeof v === 'number')),
                average: dataset.data.filter(v => typeof v === 'number')
                    .reduce((sum, val) => sum + val, 0) / dataset.data.filter(v => typeof v === 'number').length
            }));
        }

        return stats;
    }

    countDataPoints(data) {
        if (data.datasets) {
            return data.datasets.reduce((total, dataset) => total + dataset.data.length, 0);
        }
        if (Array.isArray(data)) {
            return data.length;
        }
        return 1;
    }

    getToolInfo() {
        return {
            name: 'Chart Builder',
            version: '2.0.0',
            description: 'Advanced data visualization and chart generation toolkit',
            author: 'UC2 System',
            capabilities: [
                'Multiple chart type support',
                'Interactive visualizations',
                'Multi-chart dashboards',
                'Responsive design',
                'Theme customization',
                'Animation effects',
                'Real-time data updates',
                'Export to multiple formats',
                'Statistical analysis integration',
                'Performance optimization'
            ],
            chart_types: Object.keys(this.chartTypes),
            color_palettes: Object.keys(this.colorPalettes),
            themes: Object.keys(this.themes),
            export_formats: this.exportFormats,
            animation_types: this.animationTypes,
            features: [
                'Drag-and-drop dashboard builder',
                'Cross-filtering capabilities',
                'Drill-down functionality',
                'Custom tooltip formatting',
                'Axis synchronization',
                'Legend customization',
                'Grid line configuration',
                'Data label positioning'
            ],
            performance: {
                max_data_points: 10000,
                recommended_data_points: 1000,
                supported_browsers: ['Chrome', 'Firefox', 'Safari', 'Edge']
            },
            cache_duration: '30 minutes'
        };
    }
}

module.exports = ChartBuilder;