/**
 * CSV Analyzer Tool - CSV data analysis and manipulation
 * UC2 Internal Tool v1.0.0
 * Parse, analyze, and manipulate CSV files with statistical analysis
 */

const fs = require('fs').promises;
const path = require('path');

class CSVAnalyzerTool {
    constructor() {
        this.name = 'csvAnalyzer';
        this.version = '1.0.0';
        this.description = 'Parse, analyze, and manipulate CSV files with statistical analysis';
        this.category = 'data';
        this.permissions = ['file', 'read', 'write', 'analysis'];
        this.schema = {
            type: 'object',
            properties: {
                action: {
                    type: 'string',
                    enum: ['parse', 'analyze', 'transform', 'pivot', 'filter', 'merge', 'export', 'validate'],
                    description: 'Action to perform on CSV data'
                },
                filePath: {
                    type: 'string',
                    description: 'Path to the CSV file'
                },
                data: {
                    type: 'array',
                    description: 'Raw CSV data array (alternative to filePath)'
                },
                columns: {
                    type: 'array',
                    items: { type: 'string' },
                    description: 'Specific columns to analyze or transform'
                },
                filters: {
                    type: 'object',
                    description: 'Filter conditions for data processing'
                },
                groupBy: {
                    type: 'string',
                    description: 'Column to group data by for aggregation'
                },
                aggregations: {
                    type: 'object',
                    description: 'Aggregation functions (sum, avg, count, min, max)'
                },
                outputPath: {
                    type: 'string',
                    description: 'Output path for processed data'
                },
                format: {
                    type: 'string',
                    enum: ['csv', 'json', 'xlsx'],
                    default: 'csv',
                    description: 'Output format'
                },
                delimiter: {
                    type: 'string',
                    default: ',',
                    description: 'CSV delimiter character'
                },
                hasHeader: {
                    type: 'boolean',
                    default: true,
                    description: 'Whether CSV has header row'
                },
                mergeFiles: {
                    type: 'array',
                    items: { type: 'string' },
                    description: 'Array of CSV files to merge'
                }
            },
            required: ['action']
        };

        this.mockMode = !this._checkPapaParseAvailable();
    }

    /**
     * Execute CSV processing operation
     * @param {Object} params - Processing parameters
     * @returns {Object} Processing result
     */
    async execute(params, context = {}) {
        const startTime = process.hrtime.bigint();

        try {
            const {
                action,
                filePath,
                data,
                columns,
                filters,
                groupBy,
                aggregations,
                outputPath,
                format = 'csv',
                delimiter = ',',
                hasHeader = true,
                mergeFiles
            } = params;

            // Validate action
            if (!['parse', 'analyze', 'transform', 'pivot', 'filter', 'merge', 'export', 'validate'].includes(action)) {
                throw new Error(`Invalid action: ${action}`);
            }

            let result;
            let csvData;

            // Load or use provided data
            if (data) {
                csvData = data;
            } else if (filePath) {
                csvData = await this._parseCSV(filePath, delimiter, hasHeader);
            } else {
                throw new Error('Either filePath or data must be provided');
            }

            switch (action) {
                case 'parse':
                    result = await this._parseCSV(filePath, delimiter, hasHeader);
                    break;
                case 'analyze':
                    result = await this._analyzeData(csvData, columns);
                    break;
                case 'transform':
                    result = await this._transformData(csvData, filters, columns);
                    break;
                case 'pivot':
                    result = await this._pivotData(csvData, groupBy, aggregations);
                    break;
                case 'filter':
                    result = await this._filterData(csvData, filters);
                    break;
                case 'merge':
                    result = await this._mergeCSVFiles(mergeFiles, delimiter, hasHeader);
                    break;
                case 'export':
                    result = await this._exportData(csvData, outputPath, format);
                    break;
                case 'validate':
                    result = await this._validateData(csvData, columns);
                    break;
                default:
                    throw new Error(`Unsupported action: ${action}`);
            }

            const executionTime = Number(process.hrtime.bigint() - startTime) / 1000000; // Convert to ms

            return {
                success: true,
                action: action,
                result: result,
                rowCount: Array.isArray(csvData) ? csvData.length : 0,
                timestamp: new Date().toISOString(),
                executionTime: `${executionTime.toFixed(2)}ms`,
                mockMode: this.mockMode
            };

        } catch (error) {
            return {
                success: false,
                error: error.message,
                action: params.action,
                timestamp: new Date().toISOString(),
                mockMode: this.mockMode
            };
        }
    }

    /**
     * Parse CSV file
     * @private
     */
    async _parseCSV(filePath, delimiter = ',', hasHeader = true) {
        if (!filePath) {
            throw new Error('File path is required');
        }

        if (this.mockMode) {
            return this._mockParseCSV(filePath);
        }

        try {
            // Check if file exists
            await fs.access(filePath);

            const fileContent = await fs.readFile(filePath, 'utf8');
            const Papa = require('papaparse');

            const parseResult = Papa.parse(fileContent, {
                delimiter: delimiter,
                header: hasHeader,
                skipEmptyLines: true,
                transformHeader: (header) => header.trim(),
                transform: (value) => value.trim()
            });

            if (parseResult.errors.length > 0) {
                console.warn('CSV parsing warnings:', parseResult.errors);
            }

            return {
                data: parseResult.data,
                headers: hasHeader ? Object.keys(parseResult.data[0] || {}) : null,
                rowCount: parseResult.data.length,
                errors: parseResult.errors,
                meta: parseResult.meta
            };

        } catch (error) {
            if (error.code === 'ENOENT') {
                throw new Error(`File not found: ${filePath}`);
            }
            throw new Error(`Failed to parse CSV: ${error.message}`);
        }
    }

    /**
     * Analyze CSV data with statistics
     * @private
     */
    async _analyzeData(csvData, columns = null) {
        const data = csvData.data || csvData;

        if (!Array.isArray(data) || data.length === 0) {
            throw new Error('No data to analyze');
        }

        const headers = csvData.headers || Object.keys(data[0]);
        const columnsToAnalyze = columns || headers;

        const analysis = {
            overview: {
                totalRows: data.length,
                totalColumns: headers.length,
                headers: headers
            },
            columns: {},
            dataQuality: {
                missingValues: 0,
                duplicateRows: 0,
                uniqueRows: data.length
            }
        };

        // Analyze each column
        for (const column of columnsToAnalyze) {
            if (!headers.includes(column)) {
                continue;
            }

            const values = data.map(row => row[column]).filter(val => val !== null && val !== undefined && val !== '');
            const nonEmptyValues = values.filter(val => val.toString().trim() !== '');

            analysis.columns[column] = {
                totalValues: values.length,
                nonEmptyValues: nonEmptyValues.length,
                missingValues: data.length - nonEmptyValues.length,
                uniqueValues: new Set(nonEmptyValues).size,
                dataType: this._inferDataType(nonEmptyValues),
                statistics: this._calculateStatistics(nonEmptyValues),
                distribution: this._getValueDistribution(nonEmptyValues, 10)
            };

            analysis.dataQuality.missingValues += analysis.columns[column].missingValues;
        }

        // Check for duplicate rows
        const rowStrings = data.map(row => JSON.stringify(row));
        const uniqueRowStrings = new Set(rowStrings);
        analysis.dataQuality.duplicateRows = rowStrings.length - uniqueRowStrings.size;
        analysis.dataQuality.uniqueRows = uniqueRowStrings.size;

        return analysis;
    }

    /**
     * Transform data based on filters and column selection
     * @private
     */
    async _transformData(csvData, filters = {}, columns = null) {
        let data = csvData.data || csvData;
        const headers = csvData.headers || Object.keys(data[0]);

        // Apply filters
        if (filters && Object.keys(filters).length > 0) {
            data = data.filter(row => this._matchesFilters(row, filters));
        }

        // Select specific columns
        if (columns && columns.length > 0) {
            data = data.map(row => {
                const newRow = {};
                columns.forEach(col => {
                    if (headers.includes(col)) {
                        newRow[col] = row[col];
                    }
                });
                return newRow;
            });
        }

        return {
            data: data,
            originalRowCount: (csvData.data || csvData).length,
            filteredRowCount: data.length,
            columns: columns || headers,
            filtersApplied: filters
        };
    }

    /**
     * Create pivot table from data
     * @private
     */
    async _pivotData(csvData, groupBy, aggregations = {}) {
        const data = csvData.data || csvData;

        if (!groupBy) {
            throw new Error('GroupBy column is required for pivot operation');
        }

        const headers = csvData.headers || Object.keys(data[0]);
        if (!headers.includes(groupBy)) {
            throw new Error(`GroupBy column '${groupBy}' not found in data`);
        }

        const groups = {};
        const pivotResult = {};

        // Group data by specified column
        data.forEach(row => {
            const groupValue = row[groupBy];
            if (!groups[groupValue]) {
                groups[groupValue] = [];
            }
            groups[groupValue].push(row);
        });

        // Calculate aggregations for each group
        Object.keys(groups).forEach(groupValue => {
            const groupData = groups[groupValue];
            pivotResult[groupValue] = {
                count: groupData.length,
                ...this._calculateAggregations(groupData, aggregations)
            };
        });

        return {
            pivot: pivotResult,
            groupBy: groupBy,
            groups: Object.keys(pivotResult).length,
            aggregations: aggregations
        };
    }

    /**
     * Filter data based on conditions
     * @private
     */
    async _filterData(csvData, filters) {
        if (!filters || Object.keys(filters).length === 0) {
            return csvData;
        }

        const data = csvData.data || csvData;
        const filteredData = data.filter(row => this._matchesFilters(row, filters));

        return {
            data: filteredData,
            originalCount: data.length,
            filteredCount: filteredData.length,
            filtersApplied: filters
        };
    }

    /**
     * Merge multiple CSV files
     * @private
     */
    async _mergeCSVFiles(filePaths, delimiter = ',', hasHeader = true) {
        if (!filePaths || !Array.isArray(filePaths) || filePaths.length === 0) {
            throw new Error('Array of file paths is required');
        }

        if (this.mockMode) {
            return this._mockMergeFiles(filePaths);
        }

        try {
            let mergedData = [];
            let commonHeaders = null;
            const fileResults = [];

            for (const filePath of filePaths) {
                const csvResult = await this._parseCSV(filePath, delimiter, hasHeader);

                // Check header consistency
                if (commonHeaders === null) {
                    commonHeaders = csvResult.headers;
                } else if (JSON.stringify(commonHeaders) !== JSON.stringify(csvResult.headers)) {
                    throw new Error(`Header mismatch in file: ${filePath}`);
                }

                mergedData = mergedData.concat(csvResult.data);
                fileResults.push({
                    file: path.basename(filePath),
                    rows: csvResult.rowCount
                });
            }

            return {
                data: mergedData,
                headers: commonHeaders,
                totalRows: mergedData.length,
                sourceFiles: fileResults,
                mergedFiles: filePaths.length
            };

        } catch (error) {
            throw new Error(`Failed to merge CSV files: ${error.message}`);
        }
    }

    /**
     * Export data to specified format
     * @private
     */
    async _exportData(csvData, outputPath, format = 'csv') {
        if (!outputPath) {
            throw new Error('Output path is required');
        }

        const data = csvData.data || csvData;
        const headers = csvData.headers || Object.keys(data[0]);

        let content;

        switch (format.toLowerCase()) {
            case 'csv':
                content = await this._exportToCSV(data, headers);
                break;
            case 'json':
                content = JSON.stringify(data, null, 2);
                break;
            case 'xlsx':
                // In real implementation, would use xlsx library
                content = JSON.stringify(data, null, 2);
                console.warn('XLSX export not implemented, exporting as JSON');
                break;
            default:
                throw new Error(`Unsupported export format: ${format}`);
        }

        await fs.writeFile(outputPath, content);

        return {
            outputPath: outputPath,
            format: format,
            rows: data.length,
            size: content.length,
            exported: true
        };
    }

    /**
     * Validate data quality and structure
     * @private
     */
    async _validateData(csvData, columns = null) {
        const data = csvData.data || csvData;
        const headers = csvData.headers || Object.keys(data[0]);
        const columnsToValidate = columns || headers;

        const validation = {
            isValid: true,
            issues: [],
            summary: {
                totalRows: data.length,
                validRows: 0,
                invalidRows: 0
            },
            columnValidation: {}
        };

        // Validate each column
        for (const column of columnsToValidate) {
            const columnValidation = {
                exists: headers.includes(column),
                missingValues: 0,
                invalidValues: 0,
                dataTypeConsistency: true,
                uniqueConstraintViolation: false
            };

            if (!columnValidation.exists) {
                validation.issues.push(`Column '${column}' not found in data`);
                validation.isValid = false;
                continue;
            }

            const values = data.map(row => row[column]);
            const inferredType = this._inferDataType(values.filter(v => v !== null && v !== undefined && v !== ''));

            values.forEach((value, index) => {
                if (value === null || value === undefined || value === '') {
                    columnValidation.missingValues++;
                } else if (!this._isValidType(value, inferredType)) {
                    columnValidation.invalidValues++;
                    columnValidation.dataTypeConsistency = false;
                }
            });

            validation.columnValidation[column] = columnValidation;
        }

        validation.summary.validRows = data.length - Math.max(...Object.values(validation.columnValidation).map(cv => cv.invalidValues));
        validation.summary.invalidRows = data.length - validation.summary.validRows;

        if (validation.summary.invalidRows > 0) {
            validation.isValid = false;
            validation.issues.push(`${validation.summary.invalidRows} rows contain invalid data`);
        }

        return validation;
    }

    /**
     * Helper methods
     */
    _checkPapaParseAvailable() {
        try {
            require('papaparse');
            return true;
        } catch (error) {
            console.warn('PapaParse library not available, using mock mode');
            return false;
        }
    }

    _mockParseCSV(filePath) {
        const mockData = [
            { id: '1', name: 'John Doe', age: '30', salary: '50000', department: 'Engineering' },
            { id: '2', name: 'Jane Smith', age: '25', salary: '45000', department: 'Marketing' },
            { id: '3', name: 'Bob Johnson', age: '35', salary: '60000', department: 'Engineering' },
            { id: '4', name: 'Alice Brown', age: '28', salary: '52000', department: 'Sales' },
            { id: '5', name: 'Charlie Wilson', age: '32', salary: '55000', department: 'Marketing' }
        ];

        return {
            data: mockData,
            headers: ['id', 'name', 'age', 'salary', 'department'],
            rowCount: mockData.length,
            errors: [],
            meta: { delimiter: ',' }
        };
    }

    _mockMergeFiles(filePaths) {
        const mockData = [];
        filePaths.forEach((filePath, index) => {
            mockData.push({
                id: `${index + 1}`,
                name: `User ${index + 1}`,
                value: Math.floor(Math.random() * 1000),
                source: path.basename(filePath)
            });
        });

        return {
            data: mockData,
            headers: ['id', 'name', 'value', 'source'],
            totalRows: mockData.length,
            sourceFiles: filePaths.map(fp => ({ file: path.basename(fp), rows: 1 })),
            mergedFiles: filePaths.length
        };
    }

    _inferDataType(values) {
        if (values.length === 0) return 'unknown';

        let numCount = 0;
        let dateCount = 0;
        let boolCount = 0;

        for (const value of values) {
            const str = value.toString().trim();

            if (!isNaN(str) && str !== '') {
                numCount++;
            } else if (this._isDate(str)) {
                dateCount++;
            } else if (str.toLowerCase() === 'true' || str.toLowerCase() === 'false') {
                boolCount++;
            }
        }

        const total = values.length;
        if (numCount / total > 0.8) return 'number';
        if (dateCount / total > 0.8) return 'date';
        if (boolCount / total > 0.8) return 'boolean';

        return 'string';
    }

    _isDate(str) {
        return !isNaN(Date.parse(str)) && isNaN(Number(str));
    }

    _isValidType(value, expectedType) {
        const str = value.toString().trim();

        switch (expectedType) {
            case 'number':
                return !isNaN(str) && str !== '';
            case 'date':
                return this._isDate(str);
            case 'boolean':
                return str.toLowerCase() === 'true' || str.toLowerCase() === 'false';
            case 'string':
                return true; // Any value can be a string
            default:
                return true;
        }
    }

    _calculateStatistics(values) {
        if (values.length === 0) {
            return { count: 0 };
        }

        const numericValues = values.filter(v => !isNaN(v)).map(v => parseFloat(v));

        if (numericValues.length === 0) {
            return {
                count: values.length,
                uniqueCount: new Set(values).size,
                mode: this._calculateMode(values)
            };
        }

        const sorted = [...numericValues].sort((a, b) => a - b);
        const sum = numericValues.reduce((acc, val) => acc + val, 0);
        const mean = sum / numericValues.length;

        const variance = numericValues.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / numericValues.length;
        const standardDeviation = Math.sqrt(variance);

        return {
            count: values.length,
            numericCount: numericValues.length,
            sum: sum,
            mean: mean,
            median: this._calculateMedian(sorted),
            mode: this._calculateMode(numericValues),
            min: Math.min(...numericValues),
            max: Math.max(...numericValues),
            range: Math.max(...numericValues) - Math.min(...numericValues),
            variance: variance,
            standardDeviation: standardDeviation,
            quartiles: this._calculateQuartiles(sorted)
        };
    }

    _calculateMedian(sortedArray) {
        const mid = Math.floor(sortedArray.length / 2);
        return sortedArray.length % 2 === 0
            ? (sortedArray[mid - 1] + sortedArray[mid]) / 2
            : sortedArray[mid];
    }

    _calculateMode(values) {
        const frequency = {};
        values.forEach(value => {
            frequency[value] = (frequency[value] || 0) + 1;
        });

        let maxFreq = 0;
        let modes = [];

        Object.entries(frequency).forEach(([value, freq]) => {
            if (freq > maxFreq) {
                maxFreq = freq;
                modes = [value];
            } else if (freq === maxFreq) {
                modes.push(value);
            }
        });

        return modes.length === Object.keys(frequency).length ? null : modes;
    }

    _calculateQuartiles(sortedArray) {
        if (sortedArray.length < 4) return { q1: null, q3: null };

        const q1Index = Math.floor(sortedArray.length * 0.25);
        const q3Index = Math.floor(sortedArray.length * 0.75);

        return {
            q1: sortedArray[q1Index],
            q3: sortedArray[q3Index]
        };
    }

    _getValueDistribution(values, topN = 10) {
        const frequency = {};
        values.forEach(value => {
            const key = value.toString();
            frequency[key] = (frequency[key] || 0) + 1;
        });

        return Object.entries(frequency)
            .sort((a, b) => b[1] - a[1])
            .slice(0, topN)
            .map(([value, count]) => ({ value, count, percentage: (count / values.length * 100).toFixed(2) }));
    }

    _matchesFilters(row, filters) {
        return Object.entries(filters).every(([column, condition]) => {
            const value = row[column];

            if (typeof condition === 'string' || typeof condition === 'number') {
                return value == condition;
            }

            if (typeof condition === 'object') {
                if (condition.equals !== undefined) return value == condition.equals;
                if (condition.contains !== undefined) return value.toString().toLowerCase().includes(condition.contains.toLowerCase());
                if (condition.startsWith !== undefined) return value.toString().toLowerCase().startsWith(condition.startsWith.toLowerCase());
                if (condition.endsWith !== undefined) return value.toString().toLowerCase().endsWith(condition.endsWith.toLowerCase());
                if (condition.gt !== undefined) return parseFloat(value) > parseFloat(condition.gt);
                if (condition.gte !== undefined) return parseFloat(value) >= parseFloat(condition.gte);
                if (condition.lt !== undefined) return parseFloat(value) < parseFloat(condition.lt);
                if (condition.lte !== undefined) return parseFloat(value) <= parseFloat(condition.lte);
                if (condition.in !== undefined) return condition.in.includes(value);
                if (condition.notIn !== undefined) return !condition.notIn.includes(value);
            }

            return true;
        });
    }

    _calculateAggregations(groupData, aggregations) {
        const results = {};

        Object.entries(aggregations).forEach(([column, functions]) => {
            if (!Array.isArray(functions)) {
                functions = [functions];
            }

            const values = groupData.map(row => row[column]).filter(v => v !== null && v !== undefined && v !== '');
            const numericValues = values.filter(v => !isNaN(v)).map(v => parseFloat(v));

            results[column] = {};

            functions.forEach(func => {
                switch (func) {
                    case 'sum':
                        results[column].sum = numericValues.reduce((acc, val) => acc + val, 0);
                        break;
                    case 'avg':
                    case 'mean':
                        results[column].avg = numericValues.length > 0
                            ? numericValues.reduce((acc, val) => acc + val, 0) / numericValues.length
                            : 0;
                        break;
                    case 'min':
                        results[column].min = numericValues.length > 0 ? Math.min(...numericValues) : null;
                        break;
                    case 'max':
                        results[column].max = numericValues.length > 0 ? Math.max(...numericValues) : null;
                        break;
                    case 'count':
                        results[column].count = values.length;
                        break;
                    case 'unique':
                        results[column].unique = new Set(values).size;
                        break;
                }
            });
        });

        return results;
    }

    async _exportToCSV(data, headers) {
        if (this.mockMode) {
            return headers.join(',') + '\n' + data.map(row =>
                headers.map(header => `"${row[header] || ''}"`).join(',')
            ).join('\n');
        }

        const Papa = require('papaparse');
        return Papa.unparse(data, { headers: headers });
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
            mockMode: this.mockMode,
            supportedFormats: ['csv', 'json', 'xlsx'],
            examples: [
                {
                    description: 'Parse CSV file',
                    input: { action: 'parse', filePath: '/path/to/data.csv' },
                    output: { data: [{}], headers: ['col1', 'col2'], rowCount: 100 }
                },
                {
                    description: 'Analyze data with statistics',
                    input: { action: 'analyze', filePath: '/path/to/data.csv', columns: ['age', 'salary'] },
                    output: { columns: { age: { mean: 30, median: 28 }, salary: { mean: 50000 } } }
                },
                {
                    description: 'Filter and transform data',
                    input: {
                        action: 'filter',
                        filePath: '/path/to/data.csv',
                        filters: { department: 'Engineering', age: { gt: 25 } }
                    },
                    output: { filteredCount: 25, originalCount: 100 }
                }
            ]
        };
    }

    /**
     * Validate tool configuration
     */
    validate() {
        const issues = [];

        if (!this.name || typeof this.name !== 'string') {
            issues.push('Tool name is required and must be a string');
        }

        if (!this.version || typeof this.version !== 'string') {
            issues.push('Tool version is required and must be a string');
        }

        if (!this.schema || typeof this.schema !== 'object') {
            issues.push('Tool schema is required and must be an object');
        }

        return {
            valid: issues.length === 0,
            issues: issues
        };
    }
}

// Export for CommonJS and ES6
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CSVAnalyzerTool;
} else if (typeof exports !== 'undefined') {
    exports.CSVAnalyzerTool = CSVAnalyzerTool;
}

// Also export as default for ES6 import
if (typeof window === 'undefined') {
    module.exports.default = CSVAnalyzerTool;
}