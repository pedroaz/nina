import pino from 'pino';

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
        return pino({
            level: 'silent',
            browser: {
                asObject: false,
            },
        });
    }

    // Return a logger that outputs to console when enabled
    return pino({
        level: LOG_LEVEL,
        base: { service: 'nina-web' },
        browser: {
            asObject: false,
            serialize: true,
        },
    });
};

const logger = createClientLogger();

export default logger;
