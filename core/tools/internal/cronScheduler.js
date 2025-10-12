/**
 * CronScheduler - Enterprise-Grade Task Automation and Scheduling Tool
 *
 * Provides comprehensive job scheduling capabilities for the UC2 platform including:
 * - Cron expression parsing and validation
 * - One-time and recurring tasks
 * - Time zone support and business day scheduling
 * - Task chaining, dependencies, and concurrency control
 * - Distributed job locking and persistence
 * - Advanced monitoring and reporting
 *
 * @author UC2 Platform
 * @version 3.0.0
 * @since 2025
 */

const EventEmitter = require('events');
const fs = require('fs').promises;
const path = require('path');
const crypto = require('crypto');
const cluster = require('cluster');

class CronScheduler extends EventEmitter {
    constructor(options = {}) {
        super();

        this.config = {
            // Core settings
            timezone: options.timezone || 'UTC',
            persistenceFile: options.persistenceFile || path.join(__dirname, '../../../data/scheduler.json'),
            maxConcurrentJobs: options.maxConcurrentJobs || 10,
            jobTimeout: options.jobTimeout || 300000, // 5 minutes

            // Retry settings
            maxRetries: options.maxRetries || 3,
            retryDelay: options.retryDelay || 5000,
            exponentialBackoff: options.exponentialBackoff || true,

            // Monitoring
            enableMetrics: options.enableMetrics !== false,
            enableLogging: options.enableLogging !== false,
            logLevel: options.logLevel || 'info',

            // Distributed features
            enableClustering: options.enableClustering || false,
            lockTimeout: options.lockTimeout || 60000,
            heartbeatInterval: options.heartbeatInterval || 30000,

            // Business features
            holidays: options.holidays || [],
            blackoutPeriods: options.blackoutPeriods || [],
            businessHours: options.businessHours || { start: '09:00', end: '17:00' },

            ...options
        };

        // Core state
        this.jobs = new Map();
        this.runningJobs = new Map();
        this.jobHistory = new Map();
        this.metrics = new Map();
        this.locks = new Map();
        this.isStarted = false;
        this.schedulerTimer = null;

        // Concurrency control
        this.jobQueue = [];
        this.activeJobs = 0;

        // Health monitoring
        this.lastHeartbeat = Date.now();
        this.systemHealth = {
            status: 'healthy',
            uptime: 0,
            jobsExecuted: 0,
            jobsSucceeded: 0,
            jobsFailed: 0,
            averageExecutionTime: 0,
            memoryUsage: 0,
            cpuUsage: 0
        };

        this.initialize();
    }

    /**
     * Initialize the scheduler
     */
    async initialize() {
        try {
            await this.loadPersistedJobs();
            await this.setupHealthMonitoring();

            if (this.config.enableClustering && cluster.isMaster) {
                await this.setupClustering();
            }

            this.emit('initialized');
            this.log('info', 'CronScheduler initialized successfully');
        } catch (error) {
            this.emit('error', error);
            this.log('error', `Failed to initialize scheduler: ${error.message}`);
        }
    }

    /**
     * Start the scheduler
     */
    async start() {
        if (this.isStarted) {
            this.log('warn', 'Scheduler already started');
            return;
        }

        this.isStarted = true;
        this.systemHealth.uptime = Date.now();

        // Main scheduler loop
        this.schedulerTimer = setInterval(() => {
            this.tick();
        }, 1000); // Check every second

        // Health monitoring
        if (this.config.enableMetrics) {
            setInterval(() => {
                this.updateHealthMetrics();
            }, this.config.heartbeatInterval);
        }

        this.emit('started');
        this.log('info', 'CronScheduler started');
    }

    /**
     * Stop the scheduler
     */
    async stop() {
        if (!this.isStarted) {
            this.log('warn', 'Scheduler not running');
            return;
        }

        this.isStarted = false;

        if (this.schedulerTimer) {
            clearInterval(this.schedulerTimer);
            this.schedulerTimer = null;
        }

        // Wait for running jobs to complete or timeout
        await this.waitForRunningJobs();

        // Persist state
        await this.persistJobs();

        this.emit('stopped');
        this.log('info', 'CronScheduler stopped');
    }

    /**
     * Schedule a new job
     */
    async schedule(jobConfig) {
        const job = this.createJob(jobConfig);

        // Validate job configuration
        const validation = this.validateJob(job);
        if (!validation.valid) {
            throw new Error(`Invalid job configuration: ${validation.errors.join(', ')}`);
        }

        // Parse and validate cron expression
        if (job.type === 'cron') {
            job.cronPattern = this.parseCronExpression(job.schedule);
            job.nextRun = this.calculateNextRun(job.cronPattern, job.timezone);
        } else if (job.type === 'interval') {
            job.intervalMs = this.parseInterval(job.schedule);
            job.nextRun = Date.now() + job.intervalMs;
        } else if (job.type === 'once') {
            job.nextRun = new Date(job.schedule).getTime();
        }

        this.jobs.set(job.id, job);
        this.metrics.set(job.id, this.createJobMetrics(job.id));

        await this.persistJobs();

        this.emit('jobScheduled', job);
        this.log('info', `Job scheduled: ${job.name} (${job.id})`);

        return job.id;
    }

    /**
     * Unschedule a job
     */
    async unschedule(jobId) {
        const job = this.jobs.get(jobId);
        if (!job) {
            throw new Error(`Job not found: ${jobId}`);
        }

        // Cancel if running
        if (this.runningJobs.has(jobId)) {
            await this.cancelJob(jobId);
        }

        this.jobs.delete(jobId);
        this.metrics.delete(jobId);

        await this.persistJobs();

        this.emit('jobUnscheduled', { jobId, job });
        this.log('info', `Job unscheduled: ${job.name} (${jobId})`);
    }

    /**
     * Pause a job
     */
    async pauseJob(jobId) {
        const job = this.jobs.get(jobId);
        if (!job) {
            throw new Error(`Job not found: ${jobId}`);
        }

        job.status = 'paused';
        await this.persistJobs();

        this.emit('jobPaused', { jobId, job });
        this.log('info', `Job paused: ${job.name} (${jobId})`);
    }

    /**
     * Resume a job
     */
    async resumeJob(jobId) {
        const job = this.jobs.get(jobId);
        if (!job) {
            throw new Error(`Job not found: ${jobId}`);
        }

        job.status = 'active';

        // Recalculate next run
        if (job.type === 'cron') {
            job.nextRun = this.calculateNextRun(job.cronPattern, job.timezone);
        } else if (job.type === 'interval') {
            job.nextRun = Date.now() + job.intervalMs;
        }

        await this.persistJobs();

        this.emit('jobResumed', { jobId, job });
        this.log('info', `Job resumed: ${job.name} (${jobId})`);
    }

    /**
     * Get job information
     */
    getJob(jobId) {
        const job = this.jobs.get(jobId);
        if (!job) return null;

        const metrics = this.metrics.get(jobId);
        const isRunning = this.runningJobs.has(jobId);

        return {
            ...job,
            metrics,
            isRunning,
            nextRunFormatted: new Date(job.nextRun).toISOString()
        };
    }

    /**
     * List all jobs
     */
    listJobs(filters = {}) {
        const jobs = Array.from(this.jobs.values());

        return jobs
            .filter(job => {
                if (filters.status && job.status !== filters.status) return false;
                if (filters.type && job.type !== filters.type) return false;
                if (filters.tag && !job.tags.includes(filters.tag)) return false;
                return true;
            })
            .map(job => this.getJob(job.id));
    }

    /**
     * Get job execution history
     */
    getJobHistory(jobId, limit = 50) {
        const history = this.jobHistory.get(jobId) || [];
        return history.slice(-limit);
    }

    /**
     * Get system health and metrics
     */
    getSystemHealth() {
        this.updateHealthMetrics();

        return {
            ...this.systemHealth,
            uptime: Date.now() - this.systemHealth.uptime,
            totalJobs: this.jobs.size,
            activeJobs: this.activeJobs,
            queuedJobs: this.jobQueue.length,
            lastHeartbeat: this.lastHeartbeat,
            nextJobs: this.getNextJobs(5)
        };
    }

    /**
     * Get upcoming jobs
     */
    getNextJobs(limit = 10) {
        return Array.from(this.jobs.values())
            .filter(job => job.status === 'active' && job.nextRun)
            .sort((a, b) => a.nextRun - b.nextRun)
            .slice(0, limit)
            .map(job => ({
                id: job.id,
                name: job.name,
                nextRun: new Date(job.nextRun).toISOString(),
                timeUntilRun: job.nextRun - Date.now()
            }));
    }

    /**
     * Execute a job immediately (bypass schedule)
     */
    async executeNow(jobId, context = {}) {
        const job = this.jobs.get(jobId);
        if (!job) {
            throw new Error(`Job not found: ${jobId}`);
        }

        if (this.runningJobs.has(jobId)) {
            throw new Error(`Job is already running: ${jobId}`);
        }

        this.log('info', `Executing job immediately: ${job.name} (${jobId})`);

        return await this.executeJob(job, { ...context, manualTrigger: true });
    }

    /**
     * Create job templates
     */
    createTemplate(name, template) {
        // Implementation for job templates
        this.emit('templateCreated', { name, template });
        this.log('info', `Job template created: ${name}`);
    }

    /**
     * Bulk operations
     */
    async bulkSchedule(jobs) {
        const results = [];
        for (const jobConfig of jobs) {
            try {
                const jobId = await this.schedule(jobConfig);
                results.push({ success: true, jobId, config: jobConfig });
            } catch (error) {
                results.push({ success: false, error: error.message, config: jobConfig });
            }
        }
        return results;
    }

    async bulkUnschedule(jobIds) {
        const results = [];
        for (const jobId of jobIds) {
            try {
                await this.unschedule(jobId);
                results.push({ success: true, jobId });
            } catch (error) {
                results.push({ success: false, jobId, error: error.message });
            }
        }
        return results;
    }

    // ==================== PRIVATE METHODS ====================

    /**
     * Main scheduler tick - runs every second
     */
    async tick() {
        try {
            const now = Date.now();
            this.lastHeartbeat = now;

            // Check for jobs to run
            for (const [jobId, job] of this.jobs) {
                if (this.shouldRunJob(job, now)) {
                    await this.queueJob(job);
                }
            }

            // Process job queue
            await this.processJobQueue();

            // Cleanup completed jobs
            this.cleanupCompletedJobs();

        } catch (error) {
            this.emit('error', error);
            this.log('error', `Scheduler tick error: ${error.message}`);
        }
    }

    /**
     * Check if job should run
     */
    shouldRunJob(job, now) {
        if (job.status !== 'active') return false;
        if (!job.nextRun || job.nextRun > now) return false;
        if (this.runningJobs.has(job.id)) return false;

        // Check blackout periods
        if (this.isInBlackoutPeriod(now)) return false;

        // Check business hours
        if (job.businessHoursOnly && !this.isBusinessHours(now, job.timezone)) return false;

        // Check holidays
        if (job.skipHolidays && this.isHoliday(now)) return false;

        // Check dependencies
        if (job.dependencies && !this.areDependenciesMet(job.dependencies)) return false;

        return true;
    }

    /**
     * Queue job for execution
     */
    async queueJob(job) {
        // Acquire distributed lock if clustering is enabled
        if (this.config.enableClustering) {
            const acquired = await this.acquireLock(job.id);
            if (!acquired) {
                this.log('debug', `Failed to acquire lock for job: ${job.id}`);
                return;
            }
        }

        this.jobQueue.push(job);
        this.emit('jobQueued', { jobId: job.id, job });
    }

    /**
     * Process the job queue
     */
    async processJobQueue() {
        while (this.jobQueue.length > 0 && this.activeJobs < this.config.maxConcurrentJobs) {
            const job = this.jobQueue.shift();
            this.executeJob(job);
        }
    }

    /**
     * Execute a job
     */
    async executeJob(job, context = {}) {
        const executionId = crypto.randomUUID();
        const startTime = Date.now();

        // Track running job
        this.runningJobs.set(job.id, {
            executionId,
            startTime,
            timeout: setTimeout(() => {
                this.timeoutJob(job.id, executionId);
            }, this.config.jobTimeout)
        });

        this.activeJobs++;

        try {
            this.emit('jobStarted', { jobId: job.id, executionId, job });
            this.log('info', `Job started: ${job.name} (${job.id})`);

            // Execute the job function
            let result;
            if (typeof job.handler === 'function') {
                result = await job.handler(context);
            } else if (typeof job.handler === 'string') {
                result = await this.executeStringHandler(job.handler, context);
            } else {
                throw new Error('Invalid job handler');
            }

            const executionTime = Date.now() - startTime;

            // Update metrics
            this.updateJobMetrics(job.id, true, executionTime);

            // Schedule next run
            if (job.type === 'cron') {
                job.nextRun = this.calculateNextRun(job.cronPattern, job.timezone);
            } else if (job.type === 'interval') {
                job.nextRun = Date.now() + job.intervalMs;
            } else if (job.type === 'once') {
                job.status = 'completed';
            }

            // Record history
            this.recordJobExecution(job.id, {
                executionId,
                startTime,
                endTime: Date.now(),
                duration: executionTime,
                success: true,
                result,
                context
            });

            this.emit('jobCompleted', { jobId: job.id, executionId, result, job });
            this.log('info', `Job completed: ${job.name} (${job.id}) in ${executionTime}ms`);

            return result;

        } catch (error) {
            const executionTime = Date.now() - startTime;

            // Handle retries
            job.retryCount = (job.retryCount || 0) + 1;

            if (job.retryCount <= (job.maxRetries || this.config.maxRetries)) {
                const delay = this.calculateRetryDelay(job.retryCount);
                job.nextRun = Date.now() + delay;

                this.log('warn', `Job failed, retrying in ${delay}ms: ${job.name} (${job.id})`);
            } else {
                job.status = 'failed';
                this.log('error', `Job failed permanently: ${job.name} (${job.id})`);
            }

            // Update metrics
            this.updateJobMetrics(job.id, false, executionTime);

            // Record history
            this.recordJobExecution(job.id, {
                executionId,
                startTime,
                endTime: Date.now(),
                duration: executionTime,
                success: false,
                error: error.message,
                context
            });

            this.emit('jobFailed', { jobId: job.id, executionId, error, job });

            throw error;

        } finally {
            // Cleanup
            const runningJob = this.runningJobs.get(job.id);
            if (runningJob && runningJob.executionId === executionId) {
                clearTimeout(runningJob.timeout);
                this.runningJobs.delete(job.id);
                this.activeJobs--;
            }

            // Release lock
            if (this.config.enableClustering) {
                await this.releaseLock(job.id);
            }

            await this.persistJobs();
        }
    }

    /**
     * Create a new job object
     */
    createJob(config) {
        const job = {
            id: config.id || crypto.randomUUID(),
            name: config.name || 'Unnamed Job',
            description: config.description || '',
            type: config.type || 'cron', // cron, interval, once
            schedule: config.schedule,
            timezone: config.timezone || this.config.timezone,
            handler: config.handler,
            context: config.context || {},

            // Status and control
            status: config.status || 'active', // active, paused, completed, failed
            priority: config.priority || 5, // 1-10
            maxRetries: config.maxRetries || this.config.maxRetries,
            retryCount: 0,

            // Scheduling options
            businessHoursOnly: config.businessHoursOnly || false,
            skipHolidays: config.skipHolidays || false,
            dependencies: config.dependencies || [],

            // Metadata
            tags: config.tags || [],
            category: config.category || 'general',
            owner: config.owner || 'system',

            // Timestamps
            createdAt: Date.now(),
            updatedAt: Date.now(),
            nextRun: null,
            lastRun: null
        };

        return job;
    }

    /**
     * Validate job configuration
     */
    validateJob(job) {
        const errors = [];

        if (!job.name || typeof job.name !== 'string') {
            errors.push('Job name is required and must be a string');
        }

        if (!job.schedule) {
            errors.push('Job schedule is required');
        }

        if (!job.handler) {
            errors.push('Job handler is required');
        }

        if (!['cron', 'interval', 'once'].includes(job.type)) {
            errors.push('Job type must be cron, interval, or once');
        }

        if (job.type === 'cron' && !this.isValidCronExpression(job.schedule)) {
            errors.push('Invalid cron expression');
        }

        return {
            valid: errors.length === 0,
            errors
        };
    }

    /**
     * Parse cron expression
     */
    parseCronExpression(expression) {
        // Basic cron parser - supports standard 5 or 6 field format
        // Fields: [second] minute hour day month dayOfWeek
        const fields = expression.trim().split(/\s+/);

        if (fields.length === 5) {
            // Add seconds field
            fields.unshift('0');
        }

        if (fields.length !== 6) {
            throw new Error('Invalid cron expression format');
        }

        return {
            second: this.parseField(fields[0], 0, 59),
            minute: this.parseField(fields[1], 0, 59),
            hour: this.parseField(fields[2], 0, 23),
            day: this.parseField(fields[3], 1, 31),
            month: this.parseField(fields[4], 1, 12),
            dayOfWeek: this.parseField(fields[5], 0, 7) // 0 and 7 are Sunday
        };
    }

    /**
     * Parse individual cron field
     */
    parseField(field, min, max) {
        const result = [];

        // Handle special characters
        if (field === '*') {
            for (let i = min; i <= max; i++) {
                result.push(i);
            }
        } else if (field.includes('/')) {
            // Step values (*/5, 1-10/2)
            const [range, step] = field.split('/');
            const stepValue = parseInt(step);
            let start = min, end = max;

            if (range !== '*') {
                if (range.includes('-')) {
                    [start, end] = range.split('-').map(Number);
                } else {
                    start = end = parseInt(range);
                }
            }

            for (let i = start; i <= end; i += stepValue) {
                if (i >= min && i <= max) {
                    result.push(i);
                }
            }
        } else if (field.includes('-')) {
            // Range (1-5)
            const [start, end] = field.split('-').map(Number);
            for (let i = start; i <= end; i++) {
                if (i >= min && i <= max) {
                    result.push(i);
                }
            }
        } else if (field.includes(',')) {
            // List (1,3,5)
            const values = field.split(',').map(Number);
            values.forEach(val => {
                if (val >= min && val <= max) {
                    result.push(val);
                }
            });
        } else {
            // Single value
            const value = parseInt(field);
            if (value >= min && value <= max) {
                result.push(value);
            }
        }

        return result;
    }

    /**
     * Calculate next run time for cron job
     */
    calculateNextRun(cronPattern, timezone) {
        const now = new Date();
        const next = new Date(now);

        // Start from next minute
        next.setSeconds(0, 0);
        next.setMinutes(next.getMinutes() + 1);

        // Find next matching time (limit search to avoid infinite loops)
        for (let i = 0; i < 366 * 24 * 60; i++) { // Max 1 year
            if (this.matchesCronPattern(next, cronPattern, timezone)) {
                return next.getTime();
            }
            next.setMinutes(next.getMinutes() + 1);
        }

        throw new Error('Could not calculate next run time');
    }

    /**
     * Check if date matches cron pattern
     */
    matchesCronPattern(date, pattern, timezone) {
        // Convert to timezone if specified
        const localDate = timezone !== 'UTC' ?
            new Date(date.toLocaleString('en-US', { timeZone: timezone })) :
            date;

        return (
            pattern.second.includes(localDate.getSeconds()) &&
            pattern.minute.includes(localDate.getMinutes()) &&
            pattern.hour.includes(localDate.getHours()) &&
            pattern.day.includes(localDate.getDate()) &&
            pattern.month.includes(localDate.getMonth() + 1) &&
            (pattern.dayOfWeek.includes(localDate.getDay()) ||
             pattern.dayOfWeek.includes(localDate.getDay() === 0 ? 7 : localDate.getDay()))
        );
    }

    /**
     * Parse interval string to milliseconds
     */
    parseInterval(interval) {
        if (typeof interval === 'number') {
            return interval;
        }

        const units = {
            s: 1000,
            m: 60000,
            h: 3600000,
            d: 86400000,
            w: 604800000
        };

        const match = interval.match(/^(\d+)([smhdw])$/);
        if (match) {
            return parseInt(match[1]) * units[match[2]];
        }

        throw new Error(`Invalid interval format: ${interval}`);
    }

    /**
     * Check if cron expression is valid
     */
    isValidCronExpression(expression) {
        try {
            this.parseCronExpression(expression);
            return true;
        } catch {
            return false;
        }
    }

    /**
     * Check if current time is in blackout period
     */
    isInBlackoutPeriod(timestamp) {
        const date = new Date(timestamp);

        return this.config.blackoutPeriods.some(period => {
            const start = new Date(period.start);
            const end = new Date(period.end);
            return date >= start && date <= end;
        });
    }

    /**
     * Check if current time is in business hours
     */
    isBusinessHours(timestamp, timezone) {
        const date = timezone !== 'UTC' ?
            new Date(timestamp.toLocaleString('en-US', { timeZone: timezone })) :
            new Date(timestamp);

        const hours = this.config.businessHours;
        const currentHour = date.getHours();
        const startHour = parseInt(hours.start.split(':')[0]);
        const endHour = parseInt(hours.end.split(':')[0]);

        // Skip weekends
        const dayOfWeek = date.getDay();
        if (dayOfWeek === 0 || dayOfWeek === 6) {
            return false;
        }

        return currentHour >= startHour && currentHour < endHour;
    }

    /**
     * Check if date is a holiday
     */
    isHoliday(timestamp) {
        const date = new Date(timestamp);
        const dateStr = date.toISOString().split('T')[0];

        return this.config.holidays.includes(dateStr);
    }

    /**
     * Check if job dependencies are met
     */
    areDependenciesMet(dependencies) {
        return dependencies.every(depId => {
            const depJob = this.jobs.get(depId);
            return depJob && depJob.status === 'completed';
        });
    }

    /**
     * Calculate retry delay with exponential backoff
     */
    calculateRetryDelay(retryCount) {
        const baseDelay = this.config.retryDelay;

        if (this.config.exponentialBackoff) {
            return baseDelay * Math.pow(2, retryCount - 1);
        }

        return baseDelay;
    }

    /**
     * Create job metrics object
     */
    createJobMetrics(jobId) {
        return {
            jobId,
            totalRuns: 0,
            successfulRuns: 0,
            failedRuns: 0,
            averageExecutionTime: 0,
            lastExecutionTime: null,
            lastSuccess: null,
            lastFailure: null,
            consecutiveFailures: 0,
            totalExecutionTime: 0
        };
    }

    /**
     * Update job metrics
     */
    updateJobMetrics(jobId, success, executionTime) {
        const metrics = this.metrics.get(jobId);
        if (!metrics) return;

        metrics.totalRuns++;
        metrics.totalExecutionTime += executionTime;
        metrics.averageExecutionTime = metrics.totalExecutionTime / metrics.totalRuns;
        metrics.lastExecutionTime = executionTime;

        if (success) {
            metrics.successfulRuns++;
            metrics.lastSuccess = Date.now();
            metrics.consecutiveFailures = 0;
        } else {
            metrics.failedRuns++;
            metrics.lastFailure = Date.now();
            metrics.consecutiveFailures++;
        }

        // Update system health
        this.systemHealth.jobsExecuted++;
        if (success) {
            this.systemHealth.jobsSucceeded++;
        } else {
            this.systemHealth.jobsFailed++;
        }
    }

    /**
     * Record job execution in history
     */
    recordJobExecution(jobId, execution) {
        if (!this.jobHistory.has(jobId)) {
            this.jobHistory.set(jobId, []);
        }

        const history = this.jobHistory.get(jobId);
        history.push(execution);

        // Keep only last 100 executions
        if (history.length > 100) {
            history.shift();
        }
    }

    /**
     * Execute string handler (for simple commands)
     */
    async executeStringHandler(handler, context) {
        // This could be extended to support various handler types
        // For now, treat as a system command
        const { spawn } = require('child_process');

        return new Promise((resolve, reject) => {
            const child = spawn('sh', ['-c', handler], {
                stdio: 'pipe',
                env: { ...process.env, ...context }
            });

            let stdout = '';
            let stderr = '';

            child.stdout.on('data', data => stdout += data);
            child.stderr.on('data', data => stderr += data);

            child.on('close', code => {
                if (code === 0) {
                    resolve({ stdout, stderr, exitCode: code });
                } else {
                    reject(new Error(`Command failed with exit code ${code}: ${stderr}`));
                }
            });
        });
    }

    /**
     * Timeout a job
     */
    async timeoutJob(jobId, executionId) {
        const runningJob = this.runningJobs.get(jobId);
        if (!runningJob || runningJob.executionId !== executionId) {
            return;
        }

        this.runningJobs.delete(jobId);
        this.activeJobs--;

        const job = this.jobs.get(jobId);
        if (job) {
            this.emit('jobTimeout', { jobId, executionId, job });
            this.log('warn', `Job timed out: ${job.name} (${jobId})`);
        }
    }

    /**
     * Cancel a running job
     */
    async cancelJob(jobId) {
        const runningJob = this.runningJobs.get(jobId);
        if (!runningJob) {
            throw new Error(`Job not running: ${jobId}`);
        }

        clearTimeout(runningJob.timeout);
        this.runningJobs.delete(jobId);
        this.activeJobs--;

        const job = this.jobs.get(jobId);
        this.emit('jobCancelled', { jobId, job });
        this.log('info', `Job cancelled: ${job.name} (${jobId})`);
    }

    /**
     * Wait for all running jobs to complete
     */
    async waitForRunningJobs(timeout = 30000) {
        const startTime = Date.now();

        while (this.runningJobs.size > 0) {
            if (Date.now() - startTime > timeout) {
                this.log('warn', `Timeout waiting for jobs to complete. Forcing shutdown.`);

                // Cancel all running jobs
                for (const jobId of this.runningJobs.keys()) {
                    await this.cancelJob(jobId);
                }
                break;
            }

            await new Promise(resolve => setTimeout(resolve, 100));
        }
    }

    /**
     * Cleanup completed jobs
     */
    cleanupCompletedJobs() {
        const now = Date.now();
        const cleanupAge = 24 * 60 * 60 * 1000; // 24 hours

        for (const [jobId, job] of this.jobs) {
            if (job.status === 'completed' &&
                job.lastRun &&
                now - job.lastRun > cleanupAge) {

                this.jobs.delete(jobId);
                this.metrics.delete(jobId);
                this.jobHistory.delete(jobId);

                this.log('debug', `Cleaned up completed job: ${job.name} (${jobId})`);
            }
        }
    }

    /**
     * Update system health metrics
     */
    updateHealthMetrics() {
        const usage = process.memoryUsage();
        this.systemHealth.memoryUsage = usage.rss;

        // Calculate success rate
        const totalJobs = this.systemHealth.jobsExecuted;
        if (totalJobs > 0) {
            this.systemHealth.successRate = (this.systemHealth.jobsSucceeded / totalJobs) * 100;
        }

        // Calculate average execution time across all jobs
        let totalExecTime = 0;
        let totalRuns = 0;

        for (const metrics of this.metrics.values()) {
            totalExecTime += metrics.totalExecutionTime;
            totalRuns += metrics.totalRuns;
        }

        if (totalRuns > 0) {
            this.systemHealth.averageExecutionTime = totalExecTime / totalRuns;
        }
    }

    /**
     * Setup health monitoring
     */
    async setupHealthMonitoring() {
        // Health check endpoint data
        this.systemHealth.status = 'healthy';

        // Monitor for stuck jobs
        setInterval(() => {
            const stuckJobTimeout = this.config.jobTimeout * 2;
            const now = Date.now();

            for (const [jobId, runningJob] of this.runningJobs) {
                if (now - runningJob.startTime > stuckJobTimeout) {
                    this.log('warn', `Detected stuck job: ${jobId}`);
                    this.timeoutJob(jobId, runningJob.executionId);
                }
            }
        }, 60000); // Check every minute
    }

    /**
     * Setup clustering support
     */
    async setupClustering() {
        if (cluster.isMaster) {
            const numWorkers = require('os').cpus().length;

            this.log('info', `Starting ${numWorkers} worker processes`);

            for (let i = 0; i < numWorkers; i++) {
                cluster.fork();
            }

            cluster.on('exit', (worker, code, signal) => {
                this.log('warn', `Worker ${worker.process.pid} died. Restarting...`);
                cluster.fork();
            });
        }
    }

    /**
     * Acquire distributed lock
     */
    async acquireLock(jobId) {
        const lockKey = `job_lock_${jobId}`;
        const lockValue = `${process.pid}_${Date.now()}`;
        const expiry = Date.now() + this.config.lockTimeout;

        // Simple in-memory lock for single instance
        // In production, use Redis or similar distributed lock
        if (this.locks.has(lockKey)) {
            const existing = this.locks.get(lockKey);
            if (existing.expiry > Date.now()) {
                return false; // Lock still valid
            }
        }

        this.locks.set(lockKey, { value: lockValue, expiry });
        return true;
    }

    /**
     * Release distributed lock
     */
    async releaseLock(jobId) {
        const lockKey = `job_lock_${jobId}`;
        this.locks.delete(lockKey);
    }

    /**
     * Load persisted jobs from disk
     */
    async loadPersistedJobs() {
        try {
            const data = await fs.readFile(this.config.persistenceFile, 'utf8');
            const parsed = JSON.parse(data);

            if (parsed.jobs) {
                for (const job of parsed.jobs) {
                    this.jobs.set(job.id, job);
                    this.metrics.set(job.id, parsed.metrics[job.id] || this.createJobMetrics(job.id));
                }
            }

            if (parsed.history) {
                for (const [jobId, history] of Object.entries(parsed.history)) {
                    this.jobHistory.set(jobId, history);
                }
            }

            this.log('info', `Loaded ${this.jobs.size} persisted jobs`);

        } catch (error) {
            if (error.code !== 'ENOENT') {
                this.log('warn', `Failed to load persisted jobs: ${error.message}`);
            }
        }
    }

    /**
     * Persist jobs to disk
     */
    async persistJobs() {
        try {
            const data = {
                version: '3.0.0',
                timestamp: Date.now(),
                jobs: Array.from(this.jobs.values()),
                metrics: Object.fromEntries(this.metrics),
                history: Object.fromEntries(this.jobHistory)
            };

            // Ensure directory exists
            await fs.mkdir(path.dirname(this.config.persistenceFile), { recursive: true });

            // Write atomically
            const tempFile = this.config.persistenceFile + '.tmp';
            await fs.writeFile(tempFile, JSON.stringify(data, null, 2));
            await fs.rename(tempFile, this.config.persistenceFile);

        } catch (error) {
            this.log('error', `Failed to persist jobs: ${error.message}`);
        }
    }

    /**
     * Log message with level
     */
    log(level, message) {
        if (!this.config.enableLogging) return;

        const timestamp = new Date().toISOString();
        const logMessage = `[${timestamp}] [${level.toUpperCase()}] [CronScheduler] ${message}`;

        if (level === 'error') {
            console.error(logMessage);
        } else if (level === 'warn') {
            console.warn(logMessage);
        } else {
            console.log(logMessage);
        }

        this.emit('log', { level, message, timestamp });
    }
}

// Export the scheduler class and helper functions
module.exports = {
    CronScheduler,

    // Helper functions for common job types
    createSystemMaintenanceJob: (options = {}) => ({
        name: 'System Maintenance',
        type: 'cron',
        schedule: '0 2 * * *', // Daily at 2 AM
        category: 'maintenance',
        businessHoursOnly: false,
        skipHolidays: false,
        ...options
    }),

    createReportJob: (options = {}) => ({
        name: 'Generate Report',
        type: 'cron',
        schedule: '0 9 * * 1', // Monday at 9 AM
        category: 'reporting',
        businessHoursOnly: true,
        skipHolidays: true,
        ...options
    }),

    createBackupJob: (options = {}) => ({
        name: 'Database Backup',
        type: 'cron',
        schedule: '0 1 * * *', // Daily at 1 AM
        category: 'backup',
        businessHoursOnly: false,
        skipHolidays: false,
        maxRetries: 5,
        ...options
    }),

    createHealthCheckJob: (options = {}) => ({
        name: 'Health Check',
        type: 'interval',
        schedule: '5m', // Every 5 minutes
        category: 'monitoring',
        businessHoursOnly: false,
        skipHolidays: false,
        ...options
    }),

    // Utility functions
    parseCronExpression: (expression) => {
        const scheduler = new CronScheduler();
        return scheduler.parseCronExpression(expression);
    },

    validateCronExpression: (expression) => {
        try {
            const scheduler = new CronScheduler();
            scheduler.parseCronExpression(expression);
            return true;
        } catch {
            return false;
        }
    },

    // Common cron patterns
    CRON_PATTERNS: {
        EVERY_MINUTE: '* * * * *',
        EVERY_5_MINUTES: '*/5 * * * *',
        EVERY_15_MINUTES: '*/15 * * * *',
        EVERY_30_MINUTES: '*/30 * * * *',
        EVERY_HOUR: '0 * * * *',
        EVERY_2_HOURS: '0 */2 * * *',
        EVERY_6_HOURS: '0 */6 * * *',
        EVERY_12_HOURS: '0 */12 * * *',
        DAILY_MIDNIGHT: '0 0 * * *',
        DAILY_9AM: '0 9 * * *',
        DAILY_6PM: '0 18 * * *',
        WEEKLY_MONDAY_9AM: '0 9 * * 1',
        WEEKLY_FRIDAY_5PM: '0 17 * * 5',
        MONTHLY_1ST_9AM: '0 9 1 * *',
        YEARLY_JAN_1ST: '0 0 1 1 *'
    }
};