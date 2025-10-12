/**
 * Filesystem Tool - Sandboxed file operations
 * UC2 Internal Tool v1.0.0
 */

const fs = require('fs').promises;
const path = require('path');
const crypto = require('crypto');

class FilesystemTool {
    constructor() {
        this.name = 'filesystem';
        this.version = '1.0.0';
        this.description = 'Perform sandboxed file operations with security controls';
        this.category = 'file';
        this.permissions = ['filesystem', 'read', 'write'];

        // Define sandbox directories - only allow operations within these paths
        this.sandboxPaths = [
            process.env.UC2_SANDBOX_PATH || '/tmp/uc2-sandbox',
            path.join(process.cwd(), 'data'),
            path.join(process.cwd(), 'uploads'),
            path.join(process.cwd(), 'temp')
        ];

        this.schema = {
            type: 'object',
            properties: {
                operation: {
                    type: 'string',
                    enum: ['read', 'write', 'append', 'delete', 'list', 'exists', 'info', 'mkdir', 'copy', 'move'],
                    description: 'File operation to perform'
                },
                path: {
                    type: 'string',
                    description: 'File or directory path (relative to sandbox)'
                },
                content: {
                    type: 'string',
                    description: 'Content to write (for write/append operations)'
                },
                encoding: {
                    type: 'string',
                    enum: ['utf8', 'base64', 'binary'],
                    default: 'utf8',
                    description: 'File encoding'
                },
                source: {
                    type: 'string',
                    description: 'Source path (for copy/move operations)'
                },
                destination: {
                    type: 'string',
                    description: 'Destination path (for copy/move operations)'
                },
                recursive: {
                    type: 'boolean',
                    default: false,
                    description: 'Recursive operation (for list/delete operations)'
                }
            },
            required: ['operation', 'path']
        };
    }

    /**
     * Execute filesystem operation
     */
    async execute(params, context = {}) {
        try {
            const { operation, path: filePath, content, encoding = 'utf8', source, destination, recursive = false } = params;

            // Input validation
            if (!operation || !filePath) {
                throw new Error('Operation and path are required');
            }

            // Security validation
            const safePath = this._validateAndResolvePath(filePath);
            let safeSource, safeDestination;

            if (source) {
                safeSource = this._validateAndResolvePath(source);
            }
            if (destination) {
                safeDestination = this._validateAndResolvePath(destination);
            }

            const startTime = process.hrtime.bigint();

            // Perform operation
            let result;
            switch (operation) {
                case 'read':
                    result = await this._readFile(safePath, encoding);
                    break;
                case 'write':
                    if (!content && content !== '') {
                        throw new Error('Content is required for write operations');
                    }
                    result = await this._writeFile(safePath, content, encoding);
                    break;
                case 'append':
                    if (!content && content !== '') {
                        throw new Error('Content is required for append operations');
                    }
                    result = await this._appendFile(safePath, content, encoding);
                    break;
                case 'delete':
                    result = await this._deleteFile(safePath, recursive);
                    break;
                case 'list':
                    result = await this._listDirectory(safePath, recursive);
                    break;
                case 'exists':
                    result = await this._fileExists(safePath);
                    break;
                case 'info':
                    result = await this._fileInfo(safePath);
                    break;
                case 'mkdir':
                    result = await this._createDirectory(safePath, recursive);
                    break;
                case 'copy':
                    if (!safeSource || !safeDestination) {
                        throw new Error('Source and destination are required for copy operations');
                    }
                    result = await this._copyFile(safeSource, safeDestination);
                    break;
                case 'move':
                    if (!safeSource || !safeDestination) {
                        throw new Error('Source and destination are required for move operations');
                    }
                    result = await this._moveFile(safeSource, safeDestination);
                    break;
                default:
                    throw new Error(`Unsupported operation: ${operation}`);
            }

            const executionTime = Number(process.hrtime.bigint() - startTime) / 1000000; // Convert to milliseconds

            return {
                success: true,
                operation: operation,
                path: filePath,
                result: result,
                executionTime: `${executionTime.toFixed(2)}ms`,
                timestamp: new Date().toISOString()
            };

        } catch (error) {
            return {
                success: false,
                operation: params.operation,
                path: params.path,
                error: error.message,
                timestamp: new Date().toISOString()
            };
        }
    }

    /**
     * Validate path and resolve to absolute safe path
     * @private
     */
    _validateAndResolvePath(inputPath) {
        if (!inputPath || typeof inputPath !== 'string') {
            throw new Error('Path must be a valid string');
        }

        // Prevent path traversal attacks
        if (inputPath.includes('..') || inputPath.includes('~')) {
            throw new Error('Path traversal attempts are not allowed');
        }

        // Prevent access to system files
        const dangerousPaths = ['/etc', '/usr', '/var', '/sys', '/proc', '/dev', '/boot'];
        for (const dangerous of dangerousPaths) {
            if (inputPath.startsWith(dangerous)) {
                throw new Error(`Access to system directories is not allowed: ${dangerous}`);
            }
        }

        // Resolve to absolute path within sandbox
        let resolvedPath;
        if (path.isAbsolute(inputPath)) {
            resolvedPath = inputPath;
        } else {
            // Default to first sandbox path if relative
            resolvedPath = path.resolve(this.sandboxPaths[0], inputPath);
        }

        // Check if path is within any allowed sandbox
        const isInSandbox = this.sandboxPaths.some(sandboxPath => {
            return resolvedPath.startsWith(path.resolve(sandboxPath));
        });

        if (!isInSandbox) {
            throw new Error(`Path must be within allowed sandbox directories: ${this.sandboxPaths.join(', ')}`);
        }

        return resolvedPath;
    }

    /**
     * Read file content
     * @private
     */
    async _readFile(filePath, encoding) {
        const content = await fs.readFile(filePath, encoding);
        const stats = await fs.stat(filePath);

        return {
            content: content,
            size: stats.size,
            encoding: encoding,
            checksum: this._calculateChecksum(content)
        };
    }

    /**
     * Write file content
     * @private
     */
    async _writeFile(filePath, content, encoding) {
        // Ensure directory exists
        await fs.mkdir(path.dirname(filePath), { recursive: true });

        await fs.writeFile(filePath, content, encoding);
        const stats = await fs.stat(filePath);

        return {
            bytesWritten: stats.size,
            encoding: encoding,
            checksum: this._calculateChecksum(content)
        };
    }

    /**
     * Append to file
     * @private
     */
    async _appendFile(filePath, content, encoding) {
        await fs.appendFile(filePath, content, encoding);
        const stats = await fs.stat(filePath);

        return {
            totalSize: stats.size,
            encoding: encoding,
            contentAppended: content.length
        };
    }

    /**
     * Delete file or directory
     * @private
     */
    async _deleteFile(filePath, recursive) {
        const stats = await fs.stat(filePath);

        if (stats.isDirectory()) {
            if (!recursive) {
                throw new Error('Use recursive=true to delete directories');
            }
            await fs.rmdir(filePath, { recursive: true });
            return { deleted: 'directory', path: filePath };
        } else {
            await fs.unlink(filePath);
            return { deleted: 'file', path: filePath, size: stats.size };
        }
    }

    /**
     * List directory contents
     * @private
     */
    async _listDirectory(dirPath, recursive) {
        const items = [];

        const entries = await fs.readdir(dirPath, { withFileTypes: true });

        for (const entry of entries) {
            const fullPath = path.join(dirPath, entry.name);
            const stats = await fs.stat(fullPath);

            const item = {
                name: entry.name,
                path: fullPath,
                type: entry.isDirectory() ? 'directory' : 'file',
                size: stats.size,
                modified: stats.mtime.toISOString(),
                permissions: stats.mode.toString(8)
            };

            items.push(item);

            // Recursive listing
            if (recursive && entry.isDirectory()) {
                try {
                    const subItems = await this._listDirectory(fullPath, true);
                    items.push(...subItems.items);
                } catch (error) {
                    // Skip directories we can't read
                    console.warn(`Skipping directory ${fullPath}: ${error.message}`);
                }
            }
        }

        return {
            items: items,
            count: items.length,
            path: dirPath
        };
    }

    /**
     * Check if file exists
     * @private
     */
    async _fileExists(filePath) {
        try {
            await fs.access(filePath);
            return { exists: true, path: filePath };
        } catch (error) {
            return { exists: false, path: filePath };
        }
    }

    /**
     * Get file information
     * @private
     */
    async _fileInfo(filePath) {
        const stats = await fs.stat(filePath);

        return {
            path: filePath,
            size: stats.size,
            type: stats.isDirectory() ? 'directory' : 'file',
            created: stats.birthtime.toISOString(),
            modified: stats.mtime.toISOString(),
            accessed: stats.atime.toISOString(),
            permissions: stats.mode.toString(8),
            owner: stats.uid,
            group: stats.gid
        };
    }

    /**
     * Create directory
     * @private
     */
    async _createDirectory(dirPath, recursive) {
        await fs.mkdir(dirPath, { recursive: recursive });
        return { created: dirPath, recursive: recursive };
    }

    /**
     * Copy file
     * @private
     */
    async _copyFile(sourcePath, destPath) {
        // Ensure destination directory exists
        await fs.mkdir(path.dirname(destPath), { recursive: true });

        await fs.copyFile(sourcePath, destPath);
        const sourceStats = await fs.stat(sourcePath);

        return {
            source: sourcePath,
            destination: destPath,
            size: sourceStats.size
        };
    }

    /**
     * Move file
     * @private
     */
    async _moveFile(sourcePath, destPath) {
        // Ensure destination directory exists
        await fs.mkdir(path.dirname(destPath), { recursive: true });

        const sourceStats = await fs.stat(sourcePath);
        await fs.rename(sourcePath, destPath);

        return {
            source: sourcePath,
            destination: destPath,
            size: sourceStats.size
        };
    }

    /**
     * Calculate content checksum
     * @private
     */
    _calculateChecksum(content) {
        return crypto.createHash('sha256').update(content.toString()).digest('hex');
    }

    /**
     * Initialize sandbox directories
     */
    async initialize() {
        for (const sandboxPath of this.sandboxPaths) {
            try {
                await fs.mkdir(sandboxPath, { recursive: true });
            } catch (error) {
                console.warn(`Failed to create sandbox directory ${sandboxPath}: ${error.message}`);
            }
        }
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
            sandboxPaths: this.sandboxPaths,
            supportedOperations: ['read', 'write', 'append', 'delete', 'list', 'exists', 'info', 'mkdir', 'copy', 'move'],
            examples: [
                {
                    description: 'Read a file',
                    input: { operation: 'read', path: 'data/sample.txt' },
                    output: { content: 'file content', size: 123 }
                },
                {
                    description: 'Write a file',
                    input: { operation: 'write', path: 'data/new.txt', content: 'Hello World' },
                    output: { bytesWritten: 11 }
                },
                {
                    description: 'List directory',
                    input: { operation: 'list', path: 'data', recursive: true },
                    output: { count: 5, items: [] }
                }
            ]
        };
    }

    /**
     * Validate tool configuration
     */
    validate() {
        const issues = [];

        if (!this.sandboxPaths || this.sandboxPaths.length === 0) {
            issues.push('No sandbox paths configured');
        }

        return {
            valid: issues.length === 0,
            issues: issues
        };
    }
}

module.exports = FilesystemTool;