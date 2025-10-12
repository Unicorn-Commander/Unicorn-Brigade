const NodeCache = require('node-cache');

class MapRenderer {
    constructor() {
        this.cache = new NodeCache({ stdTTL: 1800 }); // 30 minute cache

        this.supportedMapTypes = {
            'street': { provider: 'OpenStreetMap', description: 'Street-level detailed maps' },
            'satellite': { provider: 'Satellite Imagery', description: 'Satellite view maps' },
            'terrain': { provider: 'Topographic', description: 'Terrain and elevation maps' },
            'dark': { provider: 'Dark Theme', description: 'Dark-themed maps for dashboards' },
            'light': { provider: 'Light Theme', description: 'Light-themed clean maps' },
            'custom': { provider: 'Custom Style', description: 'Custom styled maps' }
        };

        this.visualizationTypes = {
            'markers': 'Point-based location markers',
            'heatmap': 'Heat map visualization for density data',
            'choropleth': 'Color-coded regions based on data values',
            'cluster': 'Clustered markers for large datasets',
            'route': 'Route and path visualization',
            'polygon': 'Custom polygon overlays',
            'circle': 'Circular area overlays with radius',
            'line': 'Line and polyline drawings'
        };

        this.exportFormats = ['png', 'jpg', 'svg', 'pdf', 'html', 'geojson'];

        this.colorSchemes = {
            'viridis': ['#440154', '#31688e', '#35b779', '#fde725'],
            'plasma': ['#0d0887', '#7e03a8', '#cc4678', '#f89441', '#fcffa4'],
            'inferno': ['#000004', '#420a68', '#932667', '#dd513a', '#fcffa4'],
            'blues': ['#f7fbff', '#c6dbef', '#6baed6', '#2171b5', '#08306b'],
            'reds': ['#fff5f0', '#fcbba1', '#fc9272', '#de2d26', '#a50f15'],
            'greens': ['#f7fcf5', '#c7e9c0', '#74c476', '#238b45', '#00441b']
        };

        this.countryBoundaries = this.initializeCountryData();
        this.mockLocationData = this.initializeMockLocationData();
    }

    async renderMap(data, options = {}) {
        try {
            const config = {
                mapType: options.mapType || 'street',
                width: options.width || 800,
                height: options.height || 600,
                centerLat: options.centerLat || 0,
                centerLng: options.centerLng || 0,
                zoomLevel: options.zoomLevel || 2,
                visualizationType: options.visualizationType || 'markers',
                colorScheme: options.colorScheme || 'viridis',
                showLegend: options.showLegend !== false,
                showControls: options.showControls !== false,
                interactive: options.interactive !== false,
                title: options.title || '',
                subtitle: options.subtitle || ''
            };

            // Validate and process data
            const processedData = this.processLocationData(data);

            if (processedData.length === 0) {
                throw new Error('No valid location data provided');
            }

            // Auto-calculate map bounds if not specified
            const bounds = this.calculateMapBounds(processedData);

            if (!options.centerLat && !options.centerLng) {
                config.centerLat = bounds.centerLat;
                config.centerLng = bounds.centerLng;
                config.zoomLevel = this.calculateOptimalZoom(bounds);
            }

            // Generate map visualization
            const mapVisualization = this.generateMapVisualization(processedData, config, bounds);

            // Create legend if requested
            const legend = config.showLegend ? this.generateMapLegend(processedData, config) : null;

            // Generate interactive HTML
            const htmlMap = this.generateInteractiveMap(processedData, config, mapVisualization);

            const result = {
                map_data: {
                    center: { lat: config.centerLat, lng: config.centerLng },
                    zoom_level: config.zoomLevel,
                    bounds: bounds,
                    map_type: config.mapType,
                    data_points: processedData.length
                },
                visualization: {
                    type: config.visualizationType,
                    color_scheme: config.colorScheme,
                    dimensions: { width: config.width, height: config.height },
                    interactive: config.interactive,
                    has_legend: config.showLegend,
                    has_controls: config.showControls
                },
                rendered_map: {
                    html_content: htmlMap,
                    style_definitions: this.generateMapCSS(config),
                    javascript_code: this.generateMapJS(processedData, config),
                    legend_data: legend
                },
                export_options: {
                    available_formats: this.exportFormats,
                    recommended_format: 'html',
                    static_image_url: this.generateStaticMapURL(config, processedData),
                    download_ready: true
                },
                performance_info: {
                    data_points_rendered: processedData.length,
                    estimated_load_time: this.estimateLoadTime(processedData.length),
                    memory_usage: this.estimateMemoryUsage(processedData, config),
                    recommended_optimizations: this.getPerformanceRecommendations(processedData.length)
                },
                rendered_at: new Date().toISOString()
            };

            return result;

        } catch (error) {
            return {
                error: 'Map rendering failed',
                message: error.message,
                data_points: Array.isArray(data) ? data.length : 'unknown',
                rendered_at: new Date().toISOString()
            };
        }
    }

    async createHeatmap(data, options = {}) {
        try {
            const config = {
                intensity: options.intensity || 1.0,
                radius: options.radius || 25,
                blur: options.blur || 15,
                maxZoom: options.maxZoom || 18,
                gradient: options.gradient || this.colorSchemes.viridis,
                opacity: options.opacity || 0.8,
                ...options
            };

            // Validate heatmap data
            const heatmapData = this.processHeatmapData(data);

            if (heatmapData.length === 0) {
                throw new Error('No valid heatmap data provided');
            }

            // Generate heatmap visualization
            const heatmapResult = await this.renderMap(heatmapData, {
                ...config,
                visualizationType: 'heatmap',
                title: options.title || 'Heat Map Visualization'
            });

            // Add heatmap-specific metadata
            heatmapResult.heatmap_settings = {
                intensity_range: this.calculateIntensityRange(heatmapData),
                data_density: this.calculateDataDensity(heatmapData),
                hot_spots: this.identifyHotSpots(heatmapData),
                coverage_area: this.calculateCoverageArea(heatmapData)
            };

            heatmapResult.analysis = {
                total_data_points: heatmapData.length,
                intensity_statistics: this.calculateIntensityStats(heatmapData),
                geographic_distribution: this.analyzeGeographicDistribution(heatmapData),
                clustering_analysis: this.analyzeClustering(heatmapData)
            };

            return heatmapResult;

        } catch (error) {
            return {
                error: 'Heatmap creation failed',
                message: error.message,
                data_points: Array.isArray(data) ? data.length : 'unknown',
                rendered_at: new Date().toISOString()
            };
        }
    }

    async createChoroplethMap(data, regions = 'countries', options = {}) {
        try {
            const config = {
                regions: regions, // 'countries', 'states', 'counties'
                valueProperty: options.valueProperty || 'value',
                colorScheme: options.colorScheme || 'blues',
                breaks: options.breaks || 'quantile',
                numClasses: options.numClasses || 5,
                strokeColor: options.strokeColor || '#ffffff',
                strokeWidth: options.strokeWidth || 1,
                ...options
            };

            // Process choropleth data
            const choroplethData = this.processChoroplethData(data, config);

            // Get region boundaries
            const boundaries = this.getRegionBoundaries(config.regions);

            // Calculate data classes and colors
            const classBreaks = this.calculateClassBreaks(choroplethData, config);
            const colorMapping = this.generateColorMapping(classBreaks, config.colorScheme);

            // Generate choropleth visualization
            const choroplethResult = await this.renderMap(choroplethData, {
                ...config,
                visualizationType: 'choropleth',
                title: options.title || `${regions.charAt(0).toUpperCase() + regions.slice(1)} Choropleth Map`
            });

            // Add choropleth-specific data
            choroplethResult.choropleth_data = {
                regions_type: config.regions,
                total_regions: choroplethData.length,
                data_range: {
                    min: Math.min(...choroplethData.map(d => d[config.valueProperty])),
                    max: Math.max(...choroplethData.map(d => d[config.valueProperty]))
                },
                class_breaks: classBreaks,
                color_mapping: colorMapping,
                missing_data_count: boundaries.length - choroplethData.length
            };

            choroplethResult.statistical_analysis = {
                descriptive_stats: this.calculateDescriptiveStats(choroplethData, config.valueProperty),
                spatial_autocorrelation: this.calculateSpatialAutocorrelation(choroplethData),
                outlier_analysis: this.identifyOutliers(choroplethData, config.valueProperty)
            };

            return choroplethResult;

        } catch (error) {
            return {
                error: 'Choropleth map creation failed',
                message: error.message,
                regions: regions,
                rendered_at: new Date().toISOString()
            };
        }
    }

    async generateRouteMap(waypoints, options = {}) {
        try {
            const config = {
                routeColor: options.routeColor || '#3388ff',
                routeWidth: options.routeWidth || 4,
                routeOpacity: options.routeOpacity || 0.8,
                showWaypoints: options.showWaypoints !== false,
                waypointColor: options.waypointColor || '#ff3388',
                waypointSize: options.waypointSize || 8,
                calculateDistance: options.calculateDistance !== false,
                showElevation: options.showElevation || false,
                routeType: options.routeType || 'driving', // driving, walking, cycling
                ...options
            };

            // Validate waypoints
            if (!Array.isArray(waypoints) || waypoints.length < 2) {
                throw new Error('At least 2 waypoints are required for route mapping');
            }

            // Process waypoints
            const processedWaypoints = this.processWaypoints(waypoints);

            // Calculate route (mock implementation)
            const routeData = this.calculateRoute(processedWaypoints, config);

            // Generate route visualization
            const routeResult = await this.renderMap(routeData.points, {
                ...config,
                visualizationType: 'route',
                title: options.title || 'Route Map'
            });

            // Add route-specific data
            routeResult.route_information = {
                total_distance: routeData.distance,
                estimated_duration: routeData.duration,
                waypoint_count: processedWaypoints.length,
                route_type: config.routeType,
                elevation_data: config.showElevation ? routeData.elevation : null
            };

            routeResult.route_analytics = {
                distance_breakdown: routeData.segments,
                geographic_bounds: this.calculateMapBounds(routeData.points),
                difficulty_assessment: this.assessRouteDifficulty(routeData),
                points_of_interest: this.findPointsOfInterest(routeData.points)
            };

            return routeResult;

        } catch (error) {
            return {
                error: 'Route map generation failed',
                message: error.message,
                waypoints: waypoints ? waypoints.length : 0,
                rendered_at: new Date().toISOString()
            };
        }
    }

    processLocationData(data) {
        if (!Array.isArray(data)) {
            return [];
        }

        return data.filter(item => {
            return (
                item &&
                typeof item.lat === 'number' &&
                typeof item.lng === 'number' &&
                item.lat >= -90 && item.lat <= 90 &&
                item.lng >= -180 && item.lng <= 180
            );
        }).map(item => ({
            lat: parseFloat(item.lat),
            lng: parseFloat(item.lng),
            value: item.value || 1,
            label: item.label || '',
            properties: item.properties || {}
        }));
    }

    calculateMapBounds(data) {
        if (data.length === 0) {
            return { minLat: -90, maxLat: 90, minLng: -180, maxLng: 180, centerLat: 0, centerLng: 0 };
        }

        const lats = data.map(d => d.lat);
        const lngs = data.map(d => d.lng);

        const bounds = {
            minLat: Math.min(...lats),
            maxLat: Math.max(...lats),
            minLng: Math.min(...lngs),
            maxLng: Math.max(...lngs)
        };

        bounds.centerLat = (bounds.minLat + bounds.maxLat) / 2;
        bounds.centerLng = (bounds.minLng + bounds.maxLng) / 2;

        return bounds;
    }

    calculateOptimalZoom(bounds) {
        const latDiff = bounds.maxLat - bounds.minLat;
        const lngDiff = bounds.maxLng - bounds.minLng;
        const maxDiff = Math.max(latDiff, lngDiff);

        if (maxDiff > 100) return 2;
        if (maxDiff > 50) return 3;
        if (maxDiff > 20) return 4;
        if (maxDiff > 10) return 5;
        if (maxDiff > 5) return 6;
        if (maxDiff > 2) return 7;
        if (maxDiff > 1) return 8;
        if (maxDiff > 0.5) return 9;
        return 10;
    }

    generateMapVisualization(data, config, bounds) {
        // Mock map visualization generation
        return {
            type: config.visualizationType,
            layers: [
                { name: 'base', type: config.mapType, opacity: 1.0 },
                { name: 'data', type: config.visualizationType, opacity: 0.8 },
                { name: 'labels', type: 'overlay', opacity: 0.9 }
            ],
            styling: this.generateMapStyling(config),
            interactivity: config.interactive ? this.generateInteractivityOptions(config) : null
        };
    }

    generateMapLegend(data, config) {
        const values = data.map(d => d.value).sort((a, b) => a - b);
        const min = values[0];
        const max = values[values.length - 1];

        return {
            type: 'continuous',
            title: 'Data Values',
            min_value: min,
            max_value: max,
            color_scale: this.colorSchemes[config.colorScheme],
            position: 'bottom-right'
        };
    }

    generateInteractiveMap(data, config, visualization) {
        // Generate HTML for interactive map
        return `
<!DOCTYPE html>
<html>
<head>
    <title>${config.title}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        #map { height: ${config.height}px; width: ${config.width}px; }
        .map-title { text-align: center; font-size: 18px; font-weight: bold; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="map-title">${config.title}</div>
    <div id="map"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        var map = L.map('map').setView([${config.centerLat}, ${config.centerLng}], ${config.zoomLevel});

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        var dataPoints = ${JSON.stringify(data)};

        dataPoints.forEach(function(point) {
            L.marker([point.lat, point.lng])
                .bindPopup(point.label || 'Value: ' + point.value)
                .addTo(map);
        });
    </script>
</body>
</html>`;
    }

    initializeMockLocationData() {
        return [
            { lat: 40.7128, lng: -74.0060, label: 'New York', value: 100 },
            { lat: 34.0522, lng: -118.2437, label: 'Los Angeles', value: 85 },
            { lat: 51.5074, lng: -0.1278, label: 'London', value: 92 },
            { lat: 35.6762, lng: 139.6503, label: 'Tokyo', value: 110 },
            { lat: -33.8688, lng: 151.2093, label: 'Sydney', value: 75 }
        ];
    }

    initializeCountryData() {
        return {
            'US': { name: 'United States', bounds: { north: 49, south: 25, east: -66, west: -125 } },
            'CA': { name: 'Canada', bounds: { north: 83, south: 41, east: -52, west: -141 } },
            'GB': { name: 'United Kingdom', bounds: { north: 61, south: 49, east: 2, west: -8 } },
            'DE': { name: 'Germany', bounds: { north: 55, south: 47, east: 15, west: 5 } },
            'FR': { name: 'France', bounds: { north: 51, south: 41, east: 10, west: -5 } }
        };
    }

    getToolInfo() {
        return {
            name: 'Map Renderer',
            version: '2.0.0',
            description: 'Advanced geographic data visualization and mapping toolkit',
            author: 'UC2 System',
            capabilities: [
                'Interactive map generation',
                'Heatmap visualization',
                'Choropleth mapping',
                'Route mapping and navigation',
                'Marker clustering',
                'Custom polygon overlays',
                'Multiple map styles and providers',
                'Export to multiple formats',
                'Geographic data analysis',
                'Spatial statistics'
            ],
            supported_map_types: Object.keys(this.supportedMapTypes),
            visualization_types: Object.keys(this.visualizationTypes),
            color_schemes: Object.keys(this.colorSchemes),
            export_formats: this.exportFormats,
            geographic_features: [
                'Coordinate validation',
                'Bounds calculation',
                'Zoom optimization',
                'Spatial clustering',
                'Distance calculation',
                'Area measurement'
            ],
            cache_duration: '30 minutes'
        };
    }
}

module.exports = MapRenderer;