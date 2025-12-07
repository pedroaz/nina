/**
 * Structured error types for better error handling
 */

export class AppError extends Error {
    constructor(
        message: string,
        public code: string,
        public statusCode: number = 500,
        public details?: unknown
    ) {
        super(message);
        this.name = this.constructor.name;
        Error.captureStackTrace(this, this.constructor);
    }
}

export class ValidationError extends AppError {
    constructor(message: string, details?: unknown) {
        super(message, 'VALIDATION_ERROR', 400, details);
    }
}

export class NotFoundError extends AppError {
    constructor(message: string, details?: unknown) {
        super(message, 'NOT_FOUND', 404, details);
    }
}

export class UnauthorizedError extends AppError {
    constructor(message: string, details?: unknown) {
        super(message, 'UNAUTHORIZED', 401, details);
    }
}

export class DatabaseError extends AppError {
    constructor(message: string, details?: unknown) {
        super(message, 'DATABASE_ERROR', 500, details);
    }
}

export class ExternalServiceError extends AppError {
    constructor(message: string, details?: unknown) {
        super(message, 'EXTERNAL_SERVICE_ERROR', 502, details);
    }
}

export class ConfigurationError extends AppError {
    constructor(message: string, details?: unknown) {
        super(message, 'CONFIGURATION_ERROR', 500, details);
    }
}
