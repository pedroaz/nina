import winston from 'winston';

/**
 * Client-side logger for web-app
 * Respects NEXT_PUBLIC_ENABLE_CLIENT_LOGS environment variable
 * When disabled, logs are silently discarded
 */

const ENABLE_CLIENT_LOGS = process.env.NEXT_PUBLIC_ENABLE_CLIENT_LOGS === 'true';
const LOG_LEVEL = process.env.NEXT_PUBLIC_LOG_LEVEL || 'info';

/**
 * Create a logger that can be disabled via environment variable
 * Useful for controlling logging in development vs. production
 */
const createClientLogger = () => {
    if (!ENABLE_CLIENT_LOGS) {
        // Return a silent logger when logs are disabled
        return winston.createLogger({
            level: 'error', // Only show critical errors
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
            transports: [
                new winston.transports.Console({
                    silent: true
                })
            ],
        });
    }

    // Return a logger that outputs to console when enabled
    return winston.createLogger({
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
        defaultMeta: { service: 'nina-web' },
        transports: [
            new winston.transports.Console()
        ],
    });
};

const logger = createClientLogger();

export default logger;
