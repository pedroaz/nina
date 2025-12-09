import pino from 'pino';

const LOG_LEVEL = process.env.LOG_LEVEL || 'info';

/**
 * Server-side logger with Pino
 * Use this in API routes, server components, and server actions
 */
export const logger = pino({
    level: LOG_LEVEL,
    base: { service: 'nina' },
    timestamp: pino.stdTimeFunctions.isoTime,
    formatters: {
        level: (label) => {
            return { level: label.toUpperCase() };
        },
    },
    // Add more server-only transports here using pino.transport()
});

export default logger;
