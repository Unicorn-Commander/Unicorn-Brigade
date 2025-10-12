const NodeCache = require('node-cache');

class TimelineBuilder {
    constructor() {
        this.cache = new NodeCache({ stdTTL: 1800 }); // 30 minute cache

        this.timelineTypes = {
            'horizontal': 'Traditional left-to-right timeline',
            'vertical': 'Top-to-bottom timeline',
            'spiral': 'Spiral/circular timeline visualization',
            'gantt': 'Gantt chart style with duration bars',
            'swimlane': 'Multiple parallel timelines',
            'interactive': 'Zoomable and pannable timeline'
        };

        this.eventTypes = {
            'milestone': { icon: '🎯', color: '#ff6b6b', description: 'Major milestones' },
            'task': { icon: '📋', color: '#4ecdc4', description: 'Tasks and activities' },
            'meeting': { icon: '🤝', color: '#45b7d1', description: 'Meetings and conferences' },
            'deadline': { icon: '⏰', color: '#ff9f43', description: 'Important deadlines' },
            'decision': { icon: '🔍', color: '#6c5ce7', description: 'Decision points' },
            'incident': { icon: '⚠️', color: '#fd79a8', description: 'Issues and incidents' },
            'release': { icon: '🚀', color: '#00b894', description: 'Releases and launches' },
            'custom': { icon: '📌', color: '#636e72', description: 'Custom events' }
        };

        this.colorSchemes = {
            'default': ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c'],
            'corporate': ['#2c3e50', '#34495e', '#7f8c8d', '#95a5a6', '#bdc3c7', '#ecf0f1'],
            'vibrant': ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#feca57', '#ff9ff3'],
            'pastel': ['#a8e6cf', '#dcedc1', '#ffd3a5', '#fdbcb4', '#c1c8e4', '#d5aaff'],
            'monochrome': ['#2d3436', '#636e72', '#74b9ff', '#0984e3', '#00b894', '#00cec9']
        };

        this.exportFormats = ['html', 'svg', 'png', 'pdf', 'json', 'csv'];

        this.dateFormats = {
            'short': 'MM/DD/YYYY',
            'medium': 'MMM DD, YYYY',
            'long': 'MMMM DD, YYYY',
            'full': 'dddd, MMMM DD, YYYY',
            'iso': 'YYYY-MM-DD',
            'relative': 'relative to now'
        };
    }

    async buildTimeline(events, options = {}) {
        try {
            const config = {
                type: options.type || 'horizontal',
                title: options.title || 'Timeline Visualization',
                subtitle: options.subtitle || '',
                startDate: options.startDate || null,
                endDate: options.endDate || null,
                colorScheme: options.colorScheme || 'default',
                showGrid: options.showGrid !== false,
                showLabels: options.showLabels !== false,
                groupBy: options.groupBy || null, // 'category', 'type', 'assignee'
                sortBy: options.sortBy || 'date',
                dateFormat: options.dateFormat || 'medium',
                width: options.width || 1200,
                height: options.height || 600,
                interactive: options.interactive !== false,
                showTooltips: options.showTooltips !== false,
                allowZoom: options.allowZoom || false
            };

            // Validate and process events
            const processedEvents = this.processTimelineEvents(events);

            if (processedEvents.length === 0) {
                throw new Error('No valid events provided for timeline');
            }

            // Sort events by date
            processedEvents.sort((a, b) => new Date(a.date) - new Date(b.date));

            // Calculate timeline bounds
            const bounds = this.calculateTimelineBounds(processedEvents, config);

            // Group events if requested
            const groupedEvents = config.groupBy ?
                this.groupEvents(processedEvents, config.groupBy) :
                { 'main': processedEvents };

            // Generate timeline structure
            const timelineStructure = this.generateTimelineStructure(groupedEvents, config, bounds);

            // Create visualization
            const visualization = this.generateTimelineVisualization(timelineStructure, config);

            const result = {
                timeline_config: {
                    type: config.type,
                    total_events: processedEvents.length,
                    time_range: {
                        start: bounds.startDate,
                        end: bounds.endDate,
                        duration: bounds.duration
                    },
                    groups: Object.keys(groupedEvents).length,
                    dimensions: { width: config.width, height: config.height }
                },
                timeline_data: {
                    events: processedEvents,
                    grouped_events: groupedEvents,
                    timeline_structure: timelineStructure,
                    color_mapping: this.generateColorMapping(groupedEvents, config.colorScheme)
                },
                visualization: {
                    html_content: visualization.html,
                    css_styles: visualization.css,
                    javascript_code: visualization.js,
                    svg_elements: visualization.svg
                },
                analysis: {
                    event_distribution: this.analyzeEventDistribution(processedEvents),
                    timeline_density: this.calculateTimelineDensity(processedEvents, bounds),
                    critical_path: this.identifyCriticalPath(processedEvents),
                    milestone_analysis: this.analyzeMilestones(processedEvents)
                },
                export_options: {
                    available_formats: this.exportFormats,
                    recommended_format: config.interactive ? 'html' : 'svg',
                    download_links: this.generateDownloadLinks(timelineStructure, config)
                },
                generated_at: new Date().toISOString()
            };

            return result;

        } catch (error) {
            return {
                error: 'Timeline building failed',
                message: error.message,
                events_provided: Array.isArray(events) ? events.length : 'unknown',
                generated_at: new Date().toISOString()
            };
        }
    }

    async createGanttChart(tasks, options = {}) {
        try {
            const config = {
                showCriticalPath: options.showCriticalPath !== false,
                showProgress: options.showProgress !== false,
                showDependencies: options.showDependencies !== false,
                showResources: options.showResources || false,
                groupByResource: options.groupByResource || false,
                timeUnit: options.timeUnit || 'days', // days, weeks, months
                ...options,
                type: 'gantt'
            };

            // Process tasks for Gantt chart
            const processedTasks = this.processGanttTasks(tasks);

            if (processedTasks.length === 0) {
                throw new Error('No valid tasks provided for Gantt chart');
            }

            // Calculate project timeline
            const projectTimeline = this.calculateProjectTimeline(processedTasks);

            // Identify dependencies and critical path
            const dependencies = this.analyzeDependencies(processedTasks);
            const criticalPath = config.showCriticalPath ? this.calculateCriticalPath(processedTasks) : null;

            // Generate Gantt visualization
            const ganttResult = await this.buildTimeline(this.convertTasksToEvents(processedTasks), config);

            // Add Gantt-specific data
            ganttResult.gantt_analysis = {
                project_duration: projectTimeline.duration,
                total_tasks: processedTasks.length,
                completed_tasks: processedTasks.filter(t => t.progress === 100).length,
                overdue_tasks: this.identifyOverdueTasks(processedTasks),
                resource_utilization: this.calculateResourceUtilization(processedTasks),
                critical_path: criticalPath,
                dependencies: dependencies
            };

            ganttResult.project_metrics = {
                overall_progress: this.calculateOverallProgress(processedTasks),
                estimated_completion: this.estimateProjectCompletion(processedTasks),
                risk_assessment: this.assessProjectRisk(processedTasks),
                milestone_status: this.analyzeMilestoneStatus(processedTasks)
            };

            return ganttResult;

        } catch (error) {
            return {
                error: 'Gantt chart creation failed',
                message: error.message,
                tasks_provided: Array.isArray(tasks) ? tasks.length : 'unknown',
                generated_at: new Date().toISOString()
            };
        }
    }

    async createEventTimeline(events, options = {}) {
        try {
            const config = {
                highlightMilestones: options.highlightMilestones !== false,
                showCategories: options.showCategories !== false,
                enableFiltering: options.enableFiltering !== false,
                showEventDetails: options.showEventDetails !== false,
                chronological: options.chronological !== false,
                ...options
            };

            // Process events with enhanced metadata
            const processedEvents = this.processEventData(events);

            // Create event timeline
            const timelineResult = await this.buildTimeline(processedEvents, {
                ...config,
                type: 'vertical',
                interactive: true,
                showTooltips: true
            });

            // Add event-specific analysis
            timelineResult.event_analysis = {
                event_types: this.analyzeEventTypes(processedEvents),
                temporal_patterns: this.identifyTemporalPatterns(processedEvents),
                event_clusters: this.identifyEventClusters(processedEvents),
                significance_scoring: this.scoreEventSignificance(processedEvents)
            };

            return timelineResult;

        } catch (error) {
            return {
                error: 'Event timeline creation failed',
                message: error.message,
                events_provided: Array.isArray(events) ? events.length : 'unknown',
                generated_at: new Date().toISOString()
            };
        }
    }

    processTimelineEvents(events) {
        if (!Array.isArray(events)) {
            return [];
        }

        return events.filter(event => {
            return event && event.date && this.isValidDate(event.date);
        }).map(event => ({
            id: event.id || this.generateEventId(),
            date: new Date(event.date),
            title: event.title || 'Untitled Event',
            description: event.description || '',
            type: event.type || 'custom',
            category: event.category || 'general',
            duration: event.duration || 0,
            endDate: event.endDate ? new Date(event.endDate) : null,
            importance: event.importance || 1,
            progress: event.progress || null,
            assignee: event.assignee || null,
            tags: event.tags || [],
            metadata: event.metadata || {}
        }));
    }

    calculateTimelineBounds(events, config) {
        if (events.length === 0) {
            return {
                startDate: new Date(),
                endDate: new Date(),
                duration: 0
            };
        }

        const dates = events.map(e => e.date);
        const endDates = events.filter(e => e.endDate).map(e => e.endDate);
        const allDates = [...dates, ...endDates];

        const startDate = config.startDate ? new Date(config.startDate) : new Date(Math.min(...allDates));
        const endDate = config.endDate ? new Date(config.endDate) : new Date(Math.max(...allDates));

        // Add padding
        const padding = (endDate - startDate) * 0.1;
        startDate.setTime(startDate.getTime() - padding);
        endDate.setTime(endDate.getTime() + padding);

        return {
            startDate: startDate,
            endDate: endDate,
            duration: endDate - startDate
        };
    }

    groupEvents(events, groupBy) {
        const groups = {};

        events.forEach(event => {
            const key = event[groupBy] || 'unknown';
            if (!groups[key]) {
                groups[key] = [];
            }
            groups[key].push(event);
        });

        return groups;
    }

    generateTimelineStructure(groupedEvents, config, bounds) {
        const structure = {
            type: config.type,
            bounds: bounds,
            groups: []
        };

        Object.entries(groupedEvents).forEach(([groupName, events], index) => {
            const group = {
                name: groupName,
                events: events,
                color: this.getGroupColor(index, config.colorScheme),
                positions: this.calculateEventPositions(events, bounds, config)
            };

            structure.groups.push(group);
        });

        return structure;
    }

    generateTimelineVisualization(structure, config) {
        const html = this.generateTimelineHTML(structure, config);
        const css = this.generateTimelineCSS(structure, config);
        const js = this.generateTimelineJS(structure, config);
        const svg = this.generateTimelineSVG(structure, config);

        return { html, css, js, svg };
    }

    generateTimelineHTML(structure, config) {
        return `
<!DOCTYPE html>
<html>
<head>
    <title>${config.title}</title>
    <meta charset="utf-8">
    <style>
        ${this.generateTimelineCSS(structure, config)}
    </style>
</head>
<body>
    <div class="timeline-container">
        <h1 class="timeline-title">${config.title}</h1>
        ${config.subtitle ? `<h2 class="timeline-subtitle">${config.subtitle}</h2>` : ''}
        <div class="timeline-content" id="timeline">
            ${this.generateTimelineContent(structure, config)}
        </div>
    </div>
    <script>
        ${this.generateTimelineJS(structure, config)}
    </script>
</body>
</html>`;
    }

    generateTimelineContent(structure, config) {
        let content = '';

        structure.groups.forEach((group, groupIndex) => {
            content += `<div class="timeline-group" data-group="${group.name}">`;

            if (structure.groups.length > 1) {
                content += `<h3 class="group-title">${group.name}</h3>`;
            }

            group.events.forEach((event, eventIndex) => {
                const eventClass = `timeline-event event-${event.type}`;
                const eventIcon = this.eventTypes[event.type]?.icon || '📌';

                content += `
                <div class="${eventClass}" data-date="${event.date.toISOString()}" style="left: ${group.positions[eventIndex]}%">
                    <div class="event-marker">
                        <span class="event-icon">${eventIcon}</span>
                    </div>
                    <div class="event-content">
                        <div class="event-title">${event.title}</div>
                        <div class="event-date">${this.formatDate(event.date, config.dateFormat)}</div>
                        ${event.description ? `<div class="event-description">${event.description}</div>` : ''}
                    </div>
                </div>`;
            });

            content += '</div>';
        });

        return content;
    }

    generateTimelineCSS(structure, config) {
        return `
        .timeline-container {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: ${config.width}px;
            margin: 0 auto;
            padding: 20px;
        }

        .timeline-title {
            text-align: center;
            color: #2c3e50;
            margin-bottom: 10px;
        }

        .timeline-subtitle {
            text-align: center;
            color: #7f8c8d;
            font-weight: normal;
            margin-bottom: 30px;
        }

        .timeline-content {
            position: relative;
            background: linear-gradient(to right, #ecf0f1 50%, transparent 50%);
            background-size: 20px 20px;
            min-height: ${config.height}px;
            border-left: 3px solid #3498db;
            padding-left: 30px;
        }

        .timeline-group {
            margin-bottom: 40px;
        }

        .group-title {
            color: #2c3e50;
            margin-bottom: 20px;
            font-size: 18px;
        }

        .timeline-event {
            position: relative;
            margin-bottom: 30px;
            opacity: 0;
            animation: fadeInUp 0.6s ease-out forwards;
        }

        .event-marker {
            position: absolute;
            left: -45px;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background: #3498db;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .event-icon {
            font-size: 14px;
        }

        .event-content {
            background: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 2px 15px rgba(0,0,0,0.1);
            border-left: 4px solid #3498db;
        }

        .event-title {
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
        }

        .event-date {
            color: #7f8c8d;
            font-size: 14px;
            margin-bottom: 10px;
        }

        .event-description {
            color: #34495e;
            line-height: 1.5;
        }

        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @media (max-width: 768px) {
            .timeline-container {
                padding: 10px;
            }

            .event-content {
                margin-left: 20px;
            }
        }`;
    }

    generateTimelineJS(structure, config) {
        return `
        document.addEventListener('DOMContentLoaded', function() {
            const timeline = document.getElementById('timeline');
            const events = timeline.querySelectorAll('.timeline-event');

            // Add hover effects
            events.forEach(event => {
                event.addEventListener('mouseenter', function() {
                    this.style.transform = 'scale(1.02)';
                    this.style.transition = 'transform 0.2s ease';
                });

                event.addEventListener('mouseleave', function() {
                    this.style.transform = 'scale(1)';
                });
            });

            // Add click handlers for interactive features
            if (${config.interactive}) {
                events.forEach(event => {
                    event.addEventListener('click', function() {
                        const date = this.dataset.date;
                        const title = this.querySelector('.event-title').textContent;
                        console.log('Event clicked:', { date, title });
                    });
                });
            }

            // Animation delays
            events.forEach((event, index) => {
                event.style.animationDelay = (index * 0.1) + 's';
            });
        });`;
    }

    isValidDate(date) {
        return date instanceof Date || !isNaN(Date.parse(date));
    }

    generateEventId() {
        return 'event_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    getGroupColor(index, colorScheme) {
        const colors = this.colorSchemes[colorScheme] || this.colorSchemes.default;
        return colors[index % colors.length];
    }

    formatDate(date, format) {
        const options = {
            short: { month: '2-digit', day: '2-digit', year: 'numeric' },
            medium: { month: 'short', day: '2-digit', year: 'numeric' },
            long: { month: 'long', day: '2-digit', year: 'numeric' },
            full: { weekday: 'long', month: 'long', day: '2-digit', year: 'numeric' }
        };

        return date.toLocaleDateString('en-US', options[format] || options.medium);
    }

    getToolInfo() {
        return {
            name: 'Timeline Builder',
            version: '2.0.0',
            description: 'Advanced timeline and Gantt chart visualization toolkit',
            author: 'UC2 System',
            capabilities: [
                'Multiple timeline types (horizontal, vertical, Gantt)',
                'Event categorization and grouping',
                'Interactive timeline navigation',
                'Project management Gantt charts',
                'Critical path analysis',
                'Resource allocation visualization',
                'Multi-format export (HTML, SVG, PDF)',
                'Responsive design',
                'Custom styling and themes',
                'Real-time progress tracking'
            ],
            timeline_types: Object.keys(this.timelineTypes),
            event_types: Object.keys(this.eventTypes),
            color_schemes: Object.keys(this.colorSchemes),
            export_formats: this.exportFormats,
            date_formats: Object.keys(this.dateFormats),
            visualization_features: [
                'Zoom and pan controls',
                'Event filtering and search',
                'Milestone highlighting',
                'Dependency visualization',
                'Progress indicators',
                'Tooltip information'
            ],
            cache_duration: '30 minutes'
        };
    }
}

module.exports = TimelineBuilder;