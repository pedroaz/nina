import winston from 'winston';

const LOG_LEVEL = process.env.LOG_LEVEL || 'info';

/**
 * Shared logger instance for backend and frontend
 * Uses console transport for both server and client logging
 * Can be extended with additional transports (file, database, HTTP, etc.) in the future
 */
const logger = winston.createLogger({
    level: LOG_LEVEL,
    format: winston.format.combine(
        winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
        winston.format.errors({ stack: true }),
        winston.format.printf(({ level, message, timestamp, ...meta }) => {
            let log = `${timestamp} [${level.toUpperCase()}]: ${message}`;
            if (Object.keys(meta).length > 0) {
                log += ` ${JSON.stringify(meta)}`;
            }
            return log;
        })
    ),
    defaultMeta: {},
    transports: [
        new winston.transports.Console()
    ],
});

export default logger;
