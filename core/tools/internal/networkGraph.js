/**
 * Network Graph Tool - Comprehensive relationship visualization and network analysis
 *
 * Features:
 * - Node and edge management
 * - Graph traversal algorithms
 * - Centrality calculations
 * - Community detection
 * - Multiple export formats
 * - Layout algorithms
 * - Temporal analysis
 * - Multi-layer networks
 */

class NetworkGraphTool {
    constructor() {
        this.nodes = new Map();
        this.edges = new Map();
        this.adjacencyList = new Map();
        this.metadata = {
            created: new Date().toISOString(),
            nodeCount: 0,
            edgeCount: 0,
            type: 'undirected',
            weighted: false,
            temporal: false
        };

        // Cache for expensive calculations
        this.cache = {
            centrality: new Map(),
            communities: null,
            paths: new Map(),
            layouts: new Map()
        };
    }

    // ============ CORE GRAPH OPERATIONS ============

    /**
     * Add a node to the graph
     */
    addNode(id, properties = {}) {
        const node = {
            id: id.toString(),
            label: properties.label || id.toString(),
            type: properties.type || 'default',
            group: properties.group || null,
            weight: properties.weight || 1,
            x: properties.x || null,
            y: properties.y || null,
            z: properties.z || null,
            color: properties.color || this._getDefaultColor(properties.type),
            size: properties.size || this._calculateNodeSize(properties),
            timestamp: properties.timestamp || new Date().toISOString(),
            metadata: properties.metadata || {},
            ...properties
        };

        this.nodes.set(node.id, node);
        this.adjacencyList.set(node.id, new Set());
        this.metadata.nodeCount = this.nodes.size;
        this._invalidateCache();

        return node;
    }

    /**
     * Add an edge between two nodes
     */
    addEdge(sourceId, targetId, properties = {}) {
        sourceId = sourceId.toString();
        targetId = targetId.toString();

        // Ensure nodes exist
        if (!this.nodes.has(sourceId) || !this.nodes.has(targetId)) {
            throw new Error(`One or both nodes do not exist: ${sourceId}, ${targetId}`);
        }

        const edgeId = properties.id || `${sourceId}-${targetId}`;
        const edge = {
            id: edgeId,
            source: sourceId,
            target: targetId,
            weight: properties.weight || 1,
            type: properties.type || 'default',
            label: properties.label || '',
            color: properties.color || '#999999',
            strength: properties.strength || properties.weight || 1,
            timestamp: properties.timestamp || new Date().toISOString(),
            directed: properties.directed || false,
            metadata: properties.metadata || {},
            ...properties
        };

        this.edges.set(edgeId, edge);

        // Update adjacency list
        this.adjacencyList.get(sourceId).add(targetId);
        if (!edge.directed) {
            this.adjacencyList.get(targetId).add(sourceId);
        }

        this.metadata.edgeCount = this.edges.size;
        if (edge.directed) this.metadata.type = 'directed';
        if (edge.weight !== 1) this.metadata.weighted = true;

        this._invalidateCache();
        return edge;
    }

    /**
     * Remove a node and all its edges
     */
    removeNode(nodeId) {
        nodeId = nodeId.toString();
        if (!this.nodes.has(nodeId)) return false;

        // Remove all edges connected to this node
        const connectedEdges = [];
        for (const [edgeId, edge] of this.edges) {
            if (edge.source === nodeId || edge.target === nodeId) {
                connectedEdges.push(edgeId);
            }
        }

        connectedEdges.forEach(edgeId => this.removeEdge(edgeId));

        // Remove the node
        this.nodes.delete(nodeId);
        this.adjacencyList.delete(nodeId);
        this.metadata.nodeCount = this.nodes.size;
        this._invalidateCache();

        return true;
    }

    /**
     * Remove an edge
     */
    removeEdge(edgeId) {
        if (!this.edges.has(edgeId)) return false;

        const edge = this.edges.get(edgeId);
        this.edges.delete(edgeId);

        // Update adjacency list
        this.adjacencyList.get(edge.source).delete(edge.target);
        if (!edge.directed) {
            this.adjacencyList.get(edge.target).delete(edge.source);
        }

        this.metadata.edgeCount = this.edges.size;
        this._invalidateCache();
        return true;
    }

    // ============ GRAPH TRAVERSAL ALGORITHMS ============

    /**
     * Breadth-first search
     */
    bfs(startNodeId, visitCallback = null) {
        startNodeId = startNodeId.toString();
        if (!this.nodes.has(startNodeId)) return [];

        const visited = new Set();
        const queue = [startNodeId];
        const result = [];

        while (queue.length > 0) {
            const nodeId = queue.shift();
            if (visited.has(nodeId)) continue;

            visited.add(nodeId);
            result.push(nodeId);

            if (visitCallback) visitCallback(this.nodes.get(nodeId));

            // Add neighbors to queue
            for (const neighborId of this.adjacencyList.get(nodeId)) {
                if (!visited.has(neighborId)) {
                    queue.push(neighborId);
                }
            }
        }

        return result;
    }

    /**
     * Depth-first search
     */
    dfs(startNodeId, visitCallback = null) {
        startNodeId = startNodeId.toString();
        if (!this.nodes.has(startNodeId)) return [];

        const visited = new Set();
        const result = [];

        const dfsRecursive = (nodeId) => {
            if (visited.has(nodeId)) return;

            visited.add(nodeId);
            result.push(nodeId);

            if (visitCallback) visitCallback(this.nodes.get(nodeId));

            for (const neighborId of this.adjacencyList.get(nodeId)) {
                dfsRecursive(neighborId);
            }
        };

        dfsRecursive(startNodeId);
        return result;
    }

    /**
     * Find shortest path using Dijkstra's algorithm
     */
    findShortestPath(startNodeId, endNodeId) {
        const cacheKey = `${startNodeId}-${endNodeId}`;
        if (this.cache.paths.has(cacheKey)) {
            return this.cache.paths.get(cacheKey);
        }

        startNodeId = startNodeId.toString();
        endNodeId = endNodeId.toString();

        const distances = new Map();
        const previous = new Map();
        const unvisited = new Set();

        // Initialize distances
        for (const nodeId of this.nodes.keys()) {
            distances.set(nodeId, nodeId === startNodeId ? 0 : Infinity);
            unvisited.add(nodeId);
        }

        while (unvisited.size > 0) {
            // Find unvisited node with minimum distance
            let current = null;
            let minDistance = Infinity;
            for (const nodeId of unvisited) {
                if (distances.get(nodeId) < minDistance) {
                    minDistance = distances.get(nodeId);
                    current = nodeId;
                }
            }

            if (current === null || minDistance === Infinity) break;
            unvisited.delete(current);

            // Check neighbors
            for (const neighborId of this.adjacencyList.get(current)) {
                if (!unvisited.has(neighborId)) continue;

                const edge = this._findEdge(current, neighborId);
                const weight = edge ? edge.weight : 1;
                const newDistance = distances.get(current) + weight;

                if (newDistance < distances.get(neighborId)) {
                    distances.set(neighborId, newDistance);
                    previous.set(neighborId, current);
                }
            }
        }

        // Reconstruct path
        const path = [];
        let current = endNodeId;
        while (current) {
            path.unshift(current);
            current = previous.get(current);
        }

        const result = {
            path: path,
            distance: distances.get(endNodeId),
            exists: distances.get(endNodeId) !== Infinity
        };

        this.cache.paths.set(cacheKey, result);
        return result;
    }

    // ============ CENTRALITY CALCULATIONS ============

    /**
     * Calculate degree centrality for all nodes
     */
    calculateDegreeCentrality() {
        if (this.cache.centrality.has('degree')) {
            return this.cache.centrality.get('degree');
        }

        const centrality = new Map();
        const maxDegree = this.nodes.size - 1;

        for (const nodeId of this.nodes.keys()) {
            const degree = this.adjacencyList.get(nodeId).size;
            centrality.set(nodeId, degree / maxDegree);
        }

        this.cache.centrality.set('degree', centrality);
        return centrality;
    }

    /**
     * Calculate betweenness centrality
     */
    calculateBetweennessCentrality() {
        if (this.cache.centrality.has('betweenness')) {
            return this.cache.centrality.get('betweenness');
        }

        const centrality = new Map();
        const nodeIds = Array.from(this.nodes.keys());

        // Initialize centrality scores
        for (const nodeId of nodeIds) {
            centrality.set(nodeId, 0);
        }

        // For each pair of nodes, calculate shortest paths
        for (let i = 0; i < nodeIds.length; i++) {
            for (let j = i + 1; j < nodeIds.length; j++) {
                const source = nodeIds[i];
                const target = nodeIds[j];

                // Find all shortest paths between source and target
                const paths = this._findAllShortestPaths(source, target);

                if (paths.length === 0) continue;

                // Count how many paths pass through each node
                for (const path of paths) {
                    for (let k = 1; k < path.length - 1; k++) {
                        const intermediateNode = path[k];
                        centrality.set(intermediateNode,
                            centrality.get(intermediateNode) + (1 / paths.length)
                        );
                    }
                }
            }
        }

        // Normalize
        const normalizationFactor = (nodeIds.length - 1) * (nodeIds.length - 2) / 2;
        for (const [nodeId, score] of centrality) {
            centrality.set(nodeId, score / normalizationFactor);
        }

        this.cache.centrality.set('betweenness', centrality);
        return centrality;
    }

    /**
     * Calculate PageRank
     */
    calculatePageRank(dampingFactor = 0.85, maxIterations = 100, tolerance = 0.0001) {
        if (this.cache.centrality.has('pagerank')) {
            return this.cache.centrality.get('pagerank');
        }

        const pageRank = new Map();
        const nodeIds = Array.from(this.nodes.keys());
        const n = nodeIds.length;

        // Initialize PageRank values
        for (const nodeId of nodeIds) {
            pageRank.set(nodeId, 1 / n);
        }

        // Iterate until convergence
        for (let iteration = 0; iteration < maxIterations; iteration++) {
            const newPageRank = new Map();
            let hasConverged = true;

            for (const nodeId of nodeIds) {
                let sum = 0;

                // Sum contributions from all nodes pointing to this node
                for (const otherNodeId of nodeIds) {
                    if (this.adjacencyList.get(otherNodeId).has(nodeId)) {
                        const outDegree = this.adjacencyList.get(otherNodeId).size;
                        if (outDegree > 0) {
                            sum += pageRank.get(otherNodeId) / outDegree;
                        }
                    }
                }

                const newValue = (1 - dampingFactor) / n + dampingFactor * sum;
                newPageRank.set(nodeId, newValue);

                // Check convergence
                if (Math.abs(newValue - pageRank.get(nodeId)) > tolerance) {
                    hasConverged = false;
                }
            }

            // Update PageRank values
            for (const [nodeId, value] of newPageRank) {
                pageRank.set(nodeId, value);
            }

            if (hasConverged) break;
        }

        this.cache.centrality.set('pagerank', pageRank);
        return pageRank;
    }

    // ============ COMMUNITY DETECTION ============

    /**
     * Louvain community detection algorithm
     */
    detectCommunities() {
        if (this.cache.communities) {
            return this.cache.communities;
        }

        const nodeIds = Array.from(this.nodes.keys());
        const communities = new Map();

        // Initialize each node in its own community
        nodeIds.forEach((nodeId, index) => {
            communities.set(nodeId, index);
        });

        let improved = true;
        let iteration = 0;
        const maxIterations = 100;

        while (improved && iteration < maxIterations) {
            improved = false;
            iteration++;

            for (const nodeId of nodeIds) {
                const currentCommunity = communities.get(nodeId);
                let bestCommunity = currentCommunity;
                let bestGain = 0;

                // Try moving node to each neighbor's community
                const neighborCommunities = new Set();
                for (const neighborId of this.adjacencyList.get(nodeId)) {
                    neighborCommunities.add(communities.get(neighborId));
                }

                for (const communityId of neighborCommunities) {
                    if (communityId === currentCommunity) continue;

                    const gain = this._calculateModularityGain(nodeId, communityId, communities);
                    if (gain > bestGain) {
                        bestGain = gain;
                        bestCommunity = communityId;
                    }
                }

                // Move node if beneficial
                if (bestCommunity !== currentCommunity) {
                    communities.set(nodeId, bestCommunity);
                    improved = true;
                }
            }
        }

        // Group nodes by community
        const communityGroups = new Map();
        for (const [nodeId, communityId] of communities) {
            if (!communityGroups.has(communityId)) {
                communityGroups.set(communityId, []);
            }
            communityGroups.get(communityId).push(nodeId);
        }

        const result = {
            communities: communities,
            groups: Array.from(communityGroups.values()),
            modularity: this._calculateModularity(communities),
            iterations: iteration
        };

        this.cache.communities = result;
        return result;
    }

    /**
     * Find cliques in the graph
     */
    findCliques(minSize = 3) {
        const cliques = [];
        const nodeIds = Array.from(this.nodes.keys());

        const isClique = (nodes) => {
            for (let i = 0; i < nodes.length; i++) {
                for (let j = i + 1; j < nodes.length; j++) {
                    if (!this.adjacencyList.get(nodes[i]).has(nodes[j])) {
                        return false;
                    }
                }
            }
            return true;
        };

        const findCliquesRecursive = (candidates, currentClique) => {
            if (candidates.length === 0) {
                if (currentClique.length >= minSize) {
                    cliques.push([...currentClique]);
                }
                return;
            }

            for (let i = 0; i < candidates.length; i++) {
                const node = candidates[i];
                const newClique = [...currentClique, node];

                if (isClique(newClique)) {
                    const newCandidates = candidates.slice(i + 1).filter(candidate =>
                        this.adjacencyList.get(node).has(candidate)
                    );
                    findCliquesRecursive(newCandidates, newClique);
                }
            }
        };

        findCliquesRecursive(nodeIds, []);
        return cliques;
    }

    // ============ LAYOUT ALGORITHMS ============

    /**
     * Force-directed layout using Fruchterman-Reingold algorithm
     */
    calculateForceDirectedLayout(width = 800, height = 600, iterations = 100) {
        const cacheKey = `force-${width}-${height}-${iterations}`;
        if (this.cache.layouts.has(cacheKey)) {
            return this.cache.layouts.get(cacheKey);
        }

        const positions = new Map();
        const nodeIds = Array.from(this.nodes.keys());
        const k = Math.sqrt((width * height) / nodeIds.length);

        // Initialize random positions
        nodeIds.forEach(nodeId => {
            positions.set(nodeId, {
                x: Math.random() * width,
                y: Math.random() * height,
                dx: 0,
                dy: 0
            });
        });

        // Simulate
        for (let iter = 0; iter < iterations; iter++) {
            const temperature = width / 10 * (1 - iter / iterations);

            // Calculate repulsive forces
            for (let i = 0; i < nodeIds.length; i++) {
                const nodeA = nodeIds[i];
                const posA = positions.get(nodeA);
                posA.dx = 0;
                posA.dy = 0;

                for (let j = 0; j < nodeIds.length; j++) {
                    if (i === j) continue;

                    const nodeB = nodeIds[j];
                    const posB = positions.get(nodeB);
                    const dx = posA.x - posB.x;
                    const dy = posA.y - posB.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);

                    if (distance > 0) {
                        const force = k * k / distance;
                        posA.dx += (dx / distance) * force;
                        posA.dy += (dy / distance) * force;
                    }
                }
            }

            // Calculate attractive forces
            for (const [edgeId, edge] of this.edges) {
                const posA = positions.get(edge.source);
                const posB = positions.get(edge.target);
                const dx = posA.x - posB.x;
                const dy = posA.y - posB.y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance > 0) {
                    const force = distance * distance / k;
                    const fx = (dx / distance) * force;
                    const fy = (dy / distance) * force;

                    posA.dx -= fx;
                    posA.dy -= fy;
                    posB.dx += fx;
                    posB.dy += fy;
                }
            }

            // Apply forces
            nodeIds.forEach(nodeId => {
                const pos = positions.get(nodeId);
                const displacement = Math.sqrt(pos.dx * pos.dx + pos.dy * pos.dy);

                if (displacement > 0) {
                    const limitedDisplacement = Math.min(displacement, temperature);
                    pos.x += (pos.dx / displacement) * limitedDisplacement;
                    pos.y += (pos.dy / displacement) * limitedDisplacement;

                    // Keep within bounds
                    pos.x = Math.max(50, Math.min(width - 50, pos.x));
                    pos.y = Math.max(50, Math.min(height - 50, pos.y));
                }
            });
        }

        const result = positions;
        this.cache.layouts.set(cacheKey, result);
        return result;
    }

    /**
     * Hierarchical layout
     */
    calculateHierarchicalLayout(rootNodeId = null, width = 800, height = 600) {
        if (!rootNodeId) {
            // Find node with highest degree centrality as root
            const centrality = this.calculateDegreeCentrality();
            rootNodeId = Array.from(centrality.entries())
                .reduce((max, [nodeId, score]) => score > max[1] ? [nodeId, score] : max, ['', 0])[0];
        }

        const positions = new Map();
        const levels = new Map();
        const visited = new Set();

        // BFS to assign levels
        const queue = [{nodeId: rootNodeId, level: 0}];
        visited.add(rootNodeId);
        levels.set(rootNodeId, 0);
        let maxLevel = 0;

        while (queue.length > 0) {
            const {nodeId, level} = queue.shift();
            maxLevel = Math.max(maxLevel, level);

            for (const neighborId of this.adjacencyList.get(nodeId)) {
                if (!visited.has(neighborId)) {
                    visited.add(neighborId);
                    levels.set(neighborId, level + 1);
                    queue.push({nodeId: neighborId, level: level + 1});
                }
            }
        }

        // Group nodes by level
        const levelGroups = new Map();
        for (const [nodeId, level] of levels) {
            if (!levelGroups.has(level)) {
                levelGroups.set(level, []);
            }
            levelGroups.get(level).push(nodeId);
        }

        // Position nodes
        const levelHeight = height / (maxLevel + 1);
        for (const [level, nodeIds] of levelGroups) {
            const nodeWidth = width / (nodeIds.length + 1);
            nodeIds.forEach((nodeId, index) => {
                positions.set(nodeId, {
                    x: nodeWidth * (index + 1),
                    y: levelHeight * (level + 0.5)
                });
            });
        }

        return positions;
    }

    // ============ EXPORT FORMATS ============

    /**
     * Export to D3.js format
     */
    toD3Format(includeLayout = true) {
        const nodes = Array.from(this.nodes.values());
        const links = Array.from(this.edges.values()).map(edge => ({
            ...edge,
            source: edge.source,
            target: edge.target
        }));

        if (includeLayout) {
            const layout = this.calculateForceDirectedLayout();
            nodes.forEach(node => {
                const pos = layout.get(node.id);
                if (pos) {
                    node.x = pos.x;
                    node.y = pos.y;
                }
            });
        }

        return {
            nodes: nodes,
            links: links,
            metadata: this.metadata
        };
    }

    /**
     * Export to Vis.js format
     */
    toVisFormat(includeLayout = true) {
        const nodes = Array.from(this.nodes.values()).map(node => ({
            id: node.id,
            label: node.label,
            group: node.group || node.type,
            color: node.color,
            size: node.size,
            x: node.x,
            y: node.y,
            physics: true,
            ...node.metadata
        }));

        const edges = Array.from(this.edges.values()).map(edge => ({
            id: edge.id,
            from: edge.source,
            to: edge.target,
            label: edge.label,
            color: edge.color,
            width: edge.weight,
            arrows: edge.directed ? 'to' : undefined,
            ...edge.metadata
        }));

        if (includeLayout) {
            const layout = this.calculateForceDirectedLayout();
            nodes.forEach(node => {
                const pos = layout.get(node.id);
                if (pos) {
                    node.x = pos.x;
                    node.y = pos.y;
                }
            });
        }

        return {
            nodes: nodes,
            edges: edges,
            options: {
                physics: {
                    enabled: !includeLayout
                }
            }
        };
    }

    /**
     * Export to Cytoscape.js format
     */
    toCytoscapeFormat(includeLayout = true) {
        const elements = [];

        // Add nodes
        for (const node of this.nodes.values()) {
            elements.push({
                data: {
                    id: node.id,
                    label: node.label,
                    type: node.type,
                    group: node.group,
                    weight: node.weight,
                    ...node.metadata
                },
                position: node.x && node.y ? {x: node.x, y: node.y} : undefined,
                style: {
                    'background-color': node.color,
                    'width': node.size,
                    'height': node.size
                }
            });
        }

        // Add edges
        for (const edge of this.edges.values()) {
            elements.push({
                data: {
                    id: edge.id,
                    source: edge.source,
                    target: edge.target,
                    label: edge.label,
                    weight: edge.weight,
                    type: edge.type,
                    ...edge.metadata
                },
                style: {
                    'line-color': edge.color,
                    'width': edge.weight,
                    'target-arrow-shape': edge.directed ? 'triangle' : 'none'
                }
            });
        }

        if (includeLayout) {
            const layout = this.calculateForceDirectedLayout();
            elements.forEach(element => {
                if (element.data.id && layout.has(element.data.id)) {
                    const pos = layout.get(element.data.id);
                    element.position = {x: pos.x, y: pos.y};
                }
            });
        }

        return {
            elements: elements,
            layout: {
                name: includeLayout ? 'preset' : 'cose'
            }
        };
    }

    /**
     * Export to GraphML format
     */
    toGraphML() {
        let graphml = '<?xml version="1.0" encoding="UTF-8"?>\n';
        graphml += '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n';
        graphml += '<graph id="G" edgedefault="undirected">\n';

        // Add nodes
        for (const node of this.nodes.values()) {
            graphml += `  <node id="${node.id}">\n`;
            graphml += `    <data key="label">${node.label}</data>\n`;
            graphml += `    <data key="type">${node.type}</data>\n`;
            if (node.x) graphml += `    <data key="x">${node.x}</data>\n`;
            if (node.y) graphml += `    <data key="y">${node.y}</data>\n`;
            graphml += `  </node>\n`;
        }

        // Add edges
        for (const edge of this.edges.values()) {
            graphml += `  <edge id="${edge.id}" source="${edge.source}" target="${edge.target}">\n`;
            graphml += `    <data key="weight">${edge.weight}</data>\n`;
            graphml += `    <data key="type">${edge.type}</data>\n`;
            graphml += `  </edge>\n`;
        }

        graphml += '</graph>\n';
        graphml += '</graphml>';

        return graphml;
    }

    /**
     * Export to DOT notation (Graphviz)
     */
    toDOTFormat() {
        const graphType = this.metadata.type === 'directed' ? 'digraph' : 'graph';
        const connector = this.metadata.type === 'directed' ? '->' : '--';

        let dot = `${graphType} G {\n`;
        dot += '  rankdir=TB;\n';
        dot += '  node [shape=circle];\n\n';

        // Add nodes
        for (const node of this.nodes.values()) {
            dot += `  "${node.id}" [label="${node.label}", color="${node.color}"];\n`;
        }

        dot += '\n';

        // Add edges
        for (const edge of this.edges.values()) {
            dot += `  "${edge.source}" ${connector} "${edge.target}"`;
            if (edge.weight !== 1) {
                dot += ` [weight=${edge.weight}]`;
            }
            dot += ';\n';
        }

        dot += '}\n';
        return dot;
    }

    // ============ ANALYSIS & STATISTICS ============

    /**
     * Generate comprehensive network statistics
     */
    getNetworkStatistics() {
        const stats = {
            basic: {
                nodeCount: this.nodes.size,
                edgeCount: this.edges.size,
                density: this._calculateDensity(),
                averageDegree: this._calculateAverageDegree(),
                isConnected: this._isConnected(),
                diameter: this._calculateDiameter(),
                radius: this._calculateRadius(),
                clustering: this._calculateClusteringCoefficient()
            },
            centrality: {
                degree: this.calculateDegreeCentrality(),
                betweenness: this.calculateBetweennessCentrality(),
                pagerank: this.calculatePageRank()
            },
            community: this.detectCommunities(),
            components: this._findConnectedComponents(),
            bridges: this._findBridges(),
            articulation: this._findArticulationPoints()
        };

        return stats;
    }

    /**
     * Generate timeline visualization data
     */
    generateTimelineData() {
        if (!this.metadata.temporal) return null;

        const events = [];

        // Node events
        for (const node of this.nodes.values()) {
            if (node.timestamp) {
                events.push({
                    id: `node-${node.id}`,
                    type: 'node_created',
                    timestamp: node.timestamp,
                    data: node,
                    description: `Node "${node.label}" created`
                });
            }
        }

        // Edge events
        for (const edge of this.edges.values()) {
            if (edge.timestamp) {
                events.push({
                    id: `edge-${edge.id}`,
                    type: 'edge_created',
                    timestamp: edge.timestamp,
                    data: edge,
                    description: `Connection between "${edge.source}" and "${edge.target}"`
                });
            }
        }

        // Sort by timestamp
        events.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        return {
            events: events,
            timeline: this._generateTimelineGroups(events)
        };
    }

    /**
     * Create interactive HTML visualization
     */
    generateInteractiveHTML(title = 'Network Visualization') {
        const d3Data = this.toD3Format();
        const stats = this.getNetworkStatistics();

        const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${title}</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            display: flex;
            gap: 20px;
        }
        .visualization {
            flex: 1;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .sidebar {
            width: 300px;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            height: fit-content;
        }
        .stats { margin-bottom: 20px; }
        .stat-item {
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            border-bottom: 1px solid #eee;
        }
        .node {
            cursor: pointer;
            stroke: #fff;
            stroke-width: 2px;
        }
        .link {
            stroke: #999;
            stroke-opacity: 0.6;
        }
        .node-label {
            font-size: 12px;
            text-anchor: middle;
            pointer-events: none;
        }
        .controls {
            margin-bottom: 20px;
        }
        button {
            padding: 8px 16px;
            margin: 4px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover {
            background: #0056b3;
        }
    </style>
</head>
<body>
    <h1>${title}</h1>
    <div class="container">
        <div class="visualization">
            <svg id="network" width="800" height="600"></svg>
        </div>
        <div class="sidebar">
            <div class="controls">
                <button onclick="restartSimulation()">Restart Layout</button>
                <button onclick="toggleLabels()">Toggle Labels</button>
                <button onclick="exportSVG()">Export SVG</button>
            </div>
            <div class="stats">
                <h3>Network Statistics</h3>
                <div class="stat-item">
                    <span>Nodes:</span>
                    <span>${stats.basic.nodeCount}</span>
                </div>
                <div class="stat-item">
                    <span>Edges:</span>
                    <span>${stats.basic.edgeCount}</span>
                </div>
                <div class="stat-item">
                    <span>Density:</span>
                    <span>${stats.basic.density.toFixed(3)}</span>
                </div>
                <div class="stat-item">
                    <span>Avg Degree:</span>
                    <span>${stats.basic.averageDegree.toFixed(2)}</span>
                </div>
                <div class="stat-item">
                    <span>Connected:</span>
                    <span>${stats.basic.isConnected ? 'Yes' : 'No'}</span>
                </div>
                <div class="stat-item">
                    <span>Communities:</span>
                    <span>${stats.community.groups.length}</span>
                </div>
            </div>
            <div id="node-info">
                <h3>Node Information</h3>
                <p>Click on a node to see details</p>
            </div>
        </div>
    </div>

    <script>
        const data = ${JSON.stringify(d3Data)};
        let showLabels = true;

        const svg = d3.select("#network");
        const width = 800;
        const height = 600;

        const simulation = d3.forceSimulation(data.nodes)
            .force("link", d3.forceLink(data.links).id(d => d.id).distance(50))
            .force("charge", d3.forceManyBody().strength(-200))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(d => d.size || 10));

        const link = svg.append("g")
            .selectAll("line")
            .data(data.links)
            .enter().append("line")
            .attr("class", "link")
            .attr("stroke-width", d => Math.sqrt(d.weight || 1));

        const node = svg.append("g")
            .selectAll("circle")
            .data(data.nodes)
            .enter().append("circle")
            .attr("class", "node")
            .attr("r", d => d.size || 8)
            .attr("fill", d => d.color || "#69b3a2")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended))
            .on("click", function(event, d) {
                showNodeInfo(d);
            });

        const label = svg.append("g")
            .selectAll("text")
            .data(data.nodes)
            .enter().append("text")
            .attr("class", "node-label")
            .text(d => d.label)
            .style("display", showLabels ? "block" : "none");

        simulation.on("tick", () => {
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);

            label
                .attr("x", d => d.x)
                .attr("y", d => d.y + 3);
        });

        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }

        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }

        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }

        function restartSimulation() {
            simulation.alpha(1).restart();
        }

        function toggleLabels() {
            showLabels = !showLabels;
            label.style("display", showLabels ? "block" : "none");
        }

        function exportSVG() {
            const svgData = new XMLSerializer().serializeToString(svg.node());
            const blob = new Blob([svgData], { type: "image/svg+xml" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = "network.svg";
            link.click();
        }

        function showNodeInfo(node) {
            const info = document.getElementById('node-info');
            info.innerHTML = \`
                <h3>Node Information</h3>
                <p><strong>ID:</strong> \${node.id}</p>
                <p><strong>Label:</strong> \${node.label}</p>
                <p><strong>Type:</strong> \${node.type}</p>
                <p><strong>Group:</strong> \${node.group || 'None'}</p>
                <p><strong>Connections:</strong> \${node.degree || 'N/A'}</p>
            \`;
        }
    </script>
</body>
</html>`;

        return html;
    }

    // ============ TEMPORAL ANALYSIS ============

    /**
     * Analyze network evolution over time
     */
    analyzeTemporalEvolution(timeWindows = 10) {
        if (!this.metadata.temporal) return null;

        const timestamps = [];

        // Collect all timestamps
        for (const node of this.nodes.values()) {
            if (node.timestamp) timestamps.push(new Date(node.timestamp));
        }
        for (const edge of this.edges.values()) {
            if (edge.timestamp) timestamps.push(new Date(edge.timestamp));
        }

        if (timestamps.length === 0) return null;

        timestamps.sort((a, b) => a - b);
        const startTime = timestamps[0];
        const endTime = timestamps[timestamps.length - 1];
        const timeSpan = endTime - startTime;
        const windowSize = timeSpan / timeWindows;

        const windows = [];
        for (let i = 0; i < timeWindows; i++) {
            const windowStart = new Date(startTime.getTime() + (i * windowSize));
            const windowEnd = new Date(startTime.getTime() + ((i + 1) * windowSize));

            const snapshot = this._createTemporalSnapshot(windowStart, windowEnd);
            windows.push({
                window: i,
                startTime: windowStart,
                endTime: windowEnd,
                nodeCount: snapshot.nodeCount,
                edgeCount: snapshot.edgeCount,
                density: snapshot.density,
                avgDegree: snapshot.avgDegree,
                components: snapshot.components.length
            });
        }

        return {
            windows: windows,
            totalTimeSpan: timeSpan,
            summary: {
                nodeGrowth: windows[windows.length - 1].nodeCount / Math.max(1, windows[0].nodeCount),
                edgeGrowth: windows[windows.length - 1].edgeCount / Math.max(1, windows[0].edgeCount),
                densityChange: windows[windows.length - 1].density - windows[0].density
            }
        };
    }

    // ============ UTILITY METHODS ============

    /**
     * Clear the graph
     */
    clear() {
        this.nodes.clear();
        this.edges.clear();
        this.adjacencyList.clear();
        this.metadata.nodeCount = 0;
        this.metadata.edgeCount = 0;
        this._invalidateCache();
    }

    /**
     * Clone the graph
     */
    clone() {
        const clone = new NetworkGraphTool();

        // Copy nodes
        for (const node of this.nodes.values()) {
            clone.addNode(node.id, {...node});
        }

        // Copy edges
        for (const edge of this.edges.values()) {
            clone.addEdge(edge.source, edge.target, {...edge});
        }

        clone.metadata = {...this.metadata};
        return clone;
    }

    /**
     * Merge another graph into this one
     */
    merge(otherGraph) {
        // Add nodes (avoiding duplicates)
        for (const node of otherGraph.nodes.values()) {
            if (!this.nodes.has(node.id)) {
                this.addNode(node.id, {...node});
            }
        }

        // Add edges (avoiding duplicates)
        for (const edge of otherGraph.edges.values()) {
            if (!this.edges.has(edge.id)) {
                this.addEdge(edge.source, edge.target, {...edge});
            }
        }

        this._invalidateCache();
    }

    /**
     * Extract subgraph containing specified nodes
     */
    extractSubgraph(nodeIds) {
        const subgraph = new NetworkGraphTool();
        nodeIds = nodeIds.map(id => id.toString());

        // Add specified nodes
        for (const nodeId of nodeIds) {
            if (this.nodes.has(nodeId)) {
                const node = this.nodes.get(nodeId);
                subgraph.addNode(nodeId, {...node});
            }
        }

        // Add edges between included nodes
        for (const edge of this.edges.values()) {
            if (nodeIds.includes(edge.source) && nodeIds.includes(edge.target)) {
                subgraph.addEdge(edge.source, edge.target, {...edge});
            }
        }

        return subgraph;
    }

    // ============ PRIVATE HELPER METHODS ============

    _invalidateCache() {
        this.cache.centrality.clear();
        this.cache.communities = null;
        this.cache.paths.clear();
        this.cache.layouts.clear();
    }

    _getDefaultColor(type) {
        const colors = {
            person: '#FF6B6B',
            organization: '#4ECDC4',
            location: '#45B7D1',
            event: '#96CEB4',
            document: '#FFEAA7',
            transaction: '#DDA0DD',
            communication: '#98D8C8',
            default: '#95A5A6'
        };
        return colors[type] || colors.default;
    }

    _calculateNodeSize(properties) {
        if (properties.size) return properties.size;
        if (properties.weight) return Math.max(8, Math.min(30, properties.weight * 5));
        return 12;
    }

    _findEdge(sourceId, targetId) {
        for (const edge of this.edges.values()) {
            if ((edge.source === sourceId && edge.target === targetId) ||
                (!edge.directed && edge.source === targetId && edge.target === sourceId)) {
                return edge;
            }
        }
        return null;
    }

    _findAllShortestPaths(startNodeId, endNodeId) {
        // Simplified version - returns single shortest path
        const result = this.findShortestPath(startNodeId, endNodeId);
        return result.exists ? [result.path] : [];
    }

    _calculateModularityGain(nodeId, newCommunityId, communities) {
        // Simplified modularity gain calculation
        const currentCommunity = communities.get(nodeId);
        let gain = 0;

        const neighbors = this.adjacencyList.get(nodeId);
        for (const neighborId of neighbors) {
            const neighborCommunity = communities.get(neighborId);
            if (neighborCommunity === newCommunityId) {
                gain += 1;
            }
            if (neighborCommunity === currentCommunity) {
                gain -= 1;
            }
        }

        return gain;
    }

    _calculateModularity(communities) {
        let modularity = 0;
        const m = this.edges.size;

        if (m === 0) return 0;

        for (const [nodeI, communityI] of communities) {
            for (const [nodeJ, communityJ] of communities) {
                if (communityI === communityJ) {
                    const hasEdge = this.adjacencyList.get(nodeI).has(nodeJ);
                    const degreeI = this.adjacencyList.get(nodeI).size;
                    const degreeJ = this.adjacencyList.get(nodeJ).size;
                    const expected = (degreeI * degreeJ) / (2 * m);

                    modularity += (hasEdge ? 1 : 0) - expected;
                }
            }
        }

        return modularity / (2 * m);
    }

    _calculateDensity() {
        const n = this.nodes.size;
        if (n < 2) return 0;
        const maxEdges = this.metadata.type === 'directed' ? n * (n - 1) : n * (n - 1) / 2;
        return this.edges.size / maxEdges;
    }

    _calculateAverageDegree() {
        if (this.nodes.size === 0) return 0;
        const totalDegree = Array.from(this.adjacencyList.values())
            .reduce((sum, neighbors) => sum + neighbors.size, 0);
        return totalDegree / this.nodes.size;
    }

    _isConnected() {
        if (this.nodes.size === 0) return true;
        const startNode = this.nodes.keys().next().value;
        const visited = new Set(this.bfs(startNode));
        return visited.size === this.nodes.size;
    }

    _calculateDiameter() {
        let maxDistance = 0;
        const nodeIds = Array.from(this.nodes.keys());

        for (let i = 0; i < nodeIds.length; i++) {
            for (let j = i + 1; j < nodeIds.length; j++) {
                const path = this.findShortestPath(nodeIds[i], nodeIds[j]);
                if (path.exists) {
                    maxDistance = Math.max(maxDistance, path.distance);
                }
            }
        }

        return maxDistance;
    }

    _calculateRadius() {
        let minMaxDistance = Infinity;
        const nodeIds = Array.from(this.nodes.keys());

        for (const nodeId of nodeIds) {
            let maxDistanceFromNode = 0;
            for (const otherId of nodeIds) {
                if (nodeId !== otherId) {
                    const path = this.findShortestPath(nodeId, otherId);
                    if (path.exists) {
                        maxDistanceFromNode = Math.max(maxDistanceFromNode, path.distance);
                    }
                }
            }
            minMaxDistance = Math.min(minMaxDistance, maxDistanceFromNode);
        }

        return minMaxDistance === Infinity ? 0 : minMaxDistance;
    }

    _calculateClusteringCoefficient() {
        let totalClustering = 0;
        let nodeCount = 0;

        for (const [nodeId, neighbors] of this.adjacencyList) {
            const degree = neighbors.size;
            if (degree < 2) continue;

            let triangles = 0;
            const neighborArray = Array.from(neighbors);

            for (let i = 0; i < neighborArray.length; i++) {
                for (let j = i + 1; j < neighborArray.length; j++) {
                    if (this.adjacencyList.get(neighborArray[i]).has(neighborArray[j])) {
                        triangles++;
                    }
                }
            }

            const possibleTriangles = degree * (degree - 1) / 2;
            totalClustering += triangles / possibleTriangles;
            nodeCount++;
        }

        return nodeCount > 0 ? totalClustering / nodeCount : 0;
    }

    _findConnectedComponents() {
        const visited = new Set();
        const components = [];

        for (const nodeId of this.nodes.keys()) {
            if (!visited.has(nodeId)) {
                const component = this.bfs(nodeId);
                component.forEach(id => visited.add(id));
                components.push(component);
            }
        }

        return components;
    }

    _findBridges() {
        const bridges = [];
        const visited = new Set();
        const disc = new Map();
        const low = new Map();
        const parent = new Map();
        let time = 0;

        const bridgeUtil = (nodeId) => {
            visited.add(nodeId);
            disc.set(nodeId, time);
            low.set(nodeId, time);
            time++;

            for (const neighborId of this.adjacencyList.get(nodeId)) {
                if (!visited.has(neighborId)) {
                    parent.set(neighborId, nodeId);
                    bridgeUtil(neighborId);

                    low.set(nodeId, Math.min(low.get(nodeId), low.get(neighborId)));

                    if (low.get(neighborId) > disc.get(nodeId)) {
                        bridges.push([nodeId, neighborId]);
                    }
                } else if (neighborId !== parent.get(nodeId)) {
                    low.set(nodeId, Math.min(low.get(nodeId), disc.get(neighborId)));
                }
            }
        };

        for (const nodeId of this.nodes.keys()) {
            if (!visited.has(nodeId)) {
                bridgeUtil(nodeId);
            }
        }

        return bridges;
    }

    _findArticulationPoints() {
        const articulationPoints = new Set();
        const visited = new Set();
        const disc = new Map();
        const low = new Map();
        const parent = new Map();
        let time = 0;

        const apUtil = (nodeId) => {
            let children = 0;
            visited.add(nodeId);
            disc.set(nodeId, time);
            low.set(nodeId, time);
            time++;

            for (const neighborId of this.adjacencyList.get(nodeId)) {
                if (!visited.has(neighborId)) {
                    parent.set(neighborId, nodeId);
                    children++;
                    apUtil(neighborId);

                    low.set(nodeId, Math.min(low.get(nodeId), low.get(neighborId)));

                    if (!parent.has(nodeId) && children > 1) {
                        articulationPoints.add(nodeId);
                    }

                    if (parent.has(nodeId) && low.get(neighborId) >= disc.get(nodeId)) {
                        articulationPoints.add(nodeId);
                    }
                } else if (neighborId !== parent.get(nodeId)) {
                    low.set(nodeId, Math.min(low.get(nodeId), disc.get(neighborId)));
                }
            }
        };

        for (const nodeId of this.nodes.keys()) {
            if (!visited.has(nodeId)) {
                apUtil(nodeId);
            }
        }

        return Array.from(articulationPoints);
    }

    _generateTimelineGroups(events) {
        const groups = new Map();

        events.forEach(event => {
            const date = new Date(event.timestamp).toDateString();
            if (!groups.has(date)) {
                groups.set(date, []);
            }
            groups.get(date).push(event);
        });

        return Array.from(groups.entries()).map(([date, events]) => ({
            date,
            events,
            count: events.length
        }));
    }

    _createTemporalSnapshot(startTime, endTime) {
        const snapshot = new NetworkGraphTool();

        // Add nodes created within time window
        for (const node of this.nodes.values()) {
            if (node.timestamp) {
                const nodeTime = new Date(node.timestamp);
                if (nodeTime >= startTime && nodeTime <= endTime) {
                    snapshot.addNode(node.id, {...node});
                }
            }
        }

        // Add edges created within time window
        for (const edge of this.edges.values()) {
            if (edge.timestamp &&
                snapshot.nodes.has(edge.source) &&
                snapshot.nodes.has(edge.target)) {
                const edgeTime = new Date(edge.timestamp);
                if (edgeTime >= startTime && edgeTime <= endTime) {
                    snapshot.addEdge(edge.source, edge.target, {...edge});
                }
            }
        }

        return {
            nodeCount: snapshot.nodes.size,
            edgeCount: snapshot.edges.size,
            density: snapshot._calculateDensity(),
            avgDegree: snapshot._calculateAverageDegree(),
            components: snapshot._findConnectedComponents()
        };
    }
}

// ============ EXPORT FUNCTIONS ============

/**
 * Create a new network graph
 */
function createNetworkGraph(options = {}) {
    const graph = new NetworkGraphTool();

    if (options.type) graph.metadata.type = options.type;
    if (options.weighted) graph.metadata.weighted = options.weighted;
    if (options.temporal) graph.metadata.temporal = options.temporal;

    return graph;
}

/**
 * Create a sample social network for demonstration
 */
function createSampleSocialNetwork() {
    const graph = createNetworkGraph({ type: 'undirected', weighted: true });

    // Add people
    const people = [
        { id: 'alice', label: 'Alice Johnson', type: 'person', group: 'family' },
        { id: 'bob', label: 'Bob Smith', type: 'person', group: 'work' },
        { id: 'charlie', label: 'Charlie Brown', type: 'person', group: 'friends' },
        { id: 'diana', label: 'Diana Prince', type: 'person', group: 'work' },
        { id: 'eve', label: 'Eve Wilson', type: 'person', group: 'family' },
        { id: 'frank', label: 'Frank Miller', type: 'person', group: 'friends' }
    ];

    people.forEach(person => graph.addNode(person.id, person));

    // Add relationships
    const relationships = [
        { source: 'alice', target: 'bob', weight: 3, type: 'colleague' },
        { source: 'alice', target: 'eve', weight: 5, type: 'family' },
        { source: 'bob', target: 'diana', weight: 4, type: 'colleague' },
        { source: 'charlie', target: 'frank', weight: 4, type: 'friend' },
        { source: 'alice', target: 'charlie', weight: 3, type: 'friend' },
        { source: 'diana', target: 'eve', weight: 2, type: 'acquaintance' }
    ];

    relationships.forEach(rel => graph.addEdge(rel.source, rel.target, rel));

    return graph;
}

/**
 * Create a sample financial network
 */
function createSampleFinancialNetwork() {
    const graph = createNetworkGraph({ type: 'directed', weighted: true, temporal: true });

    // Add accounts
    const accounts = [
        { id: 'acc1', label: 'Personal Checking', type: 'account', group: 'personal' },
        { id: 'acc2', label: 'Business Account', type: 'account', group: 'business' },
        { id: 'acc3', label: 'Savings', type: 'account', group: 'personal' },
        { id: 'acc4', label: 'Investment Fund', type: 'account', group: 'investment' }
    ];

    accounts.forEach(acc => graph.addNode(acc.id, acc));

    // Add transactions
    const transactions = [
        {
            source: 'acc1',
            target: 'acc2',
            weight: 5000,
            type: 'transfer',
            timestamp: '2024-01-15T10:00:00Z'
        },
        {
            source: 'acc1',
            target: 'acc3',
            weight: 2000,
            type: 'savings',
            timestamp: '2024-01-20T14:30:00Z'
        },
        {
            source: 'acc3',
            target: 'acc4',
            weight: 10000,
            type: 'investment',
            timestamp: '2024-02-01T09:15:00Z'
        }
    ];

    transactions.forEach(txn => graph.addEdge(txn.source, txn.target, txn));

    return graph;
}

/**
 * Main analysis function
 */
function analyzeNetworkRelationships(data, options = {}) {
    try {
        const graph = createNetworkGraph(options);

        // Parse input data
        if (data.nodes && data.edges) {
            // Standard format
            data.nodes.forEach(node => graph.addNode(node.id, node));
            data.edges.forEach(edge => graph.addEdge(edge.source, edge.target, edge));
        } else if (Array.isArray(data)) {
            // Array of relationships
            const nodeSet = new Set();
            data.forEach(rel => {
                nodeSet.add(rel.source);
                nodeSet.add(rel.target);
            });

            nodeSet.forEach(nodeId => graph.addNode(nodeId, { label: nodeId }));
            data.forEach(rel => graph.addEdge(rel.source, rel.target, rel));
        }

        // Perform analysis
        const analysis = {
            graph: graph,
            statistics: graph.getNetworkStatistics(),
            layouts: {
                forceDirected: graph.calculateForceDirectedLayout(),
                hierarchical: graph.calculateHierarchicalLayout()
            },
            exports: {
                d3: graph.toD3Format(),
                vis: graph.toVisFormat(),
                cytoscape: graph.toCytoscapeFormat(),
                graphml: graph.toGraphML(),
                dot: graph.toDOTFormat()
            },
            html: graph.generateInteractiveHTML()
        };

        // Add temporal analysis if temporal data exists
        if (graph.metadata.temporal) {
            analysis.temporal = graph.analyzeTemporalEvolution();
            analysis.timeline = graph.generateTimelineData();
        }

        return analysis;

    } catch (error) {
        return {
            error: error.message,
            success: false
        };
    }
}

module.exports = {
    NetworkGraphTool,
    createNetworkGraph,
    createSampleSocialNetwork,
    createSampleFinancialNetwork,
    analyzeNetworkRelationships
};