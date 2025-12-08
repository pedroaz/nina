import { SessionData, SessionStore } from 'genkit/beta';
import { logger } from '../logger';

/**
 * In-memory session store with FIFO eviction.
 * Sessions are kept in memory and old sessions are removed when capacity is reached.
 */
export class MemorySessionStore<S = any> implements SessionStore<S> {
    private sessions: Map<string, SessionData<S>> = new Map();
    private sessionOrder: string[] = [];
    private readonly maxSessions: number;

    constructor(maxSessions: number = 100) {
        this.maxSessions = maxSessions;
    }

    async get(sessionId: string): Promise<SessionData<S> | undefined> {
        const session = this.sessions.get(sessionId);
        if (session) {
            logger.debug(`[SessionStore] Retrieved session ${sessionId}`);
        } else {
            logger.debug(`[SessionStore] Session not found: ${sessionId}. Available sessions: ${Array.from(this.sessions.keys()).join(', ')}`);
        }
        return session;
    }

    async save(sessionId: string, sessionData: SessionData<S>): Promise<void> {
        // If session already exists, remove it from order tracking
        if (this.sessions.has(sessionId)) {
            const idx = this.sessionOrder.indexOf(sessionId);
            if (idx > -1) {
                this.sessionOrder.splice(idx, 1);
            }
        }

        // Add session to store and order tracking
        this.sessions.set(sessionId, sessionData);
        this.sessionOrder.push(sessionId);

        logger.info(`[SessionStore] Saved session ${sessionId}. Total sessions: ${this.sessions.size}`);

        // If we exceed max sessions, remove the oldest one (FIFO)
        if (this.sessions.size > this.maxSessions) {
            const oldestSessionId = this.sessionOrder.shift();
            if (oldestSessionId) {
                this.sessions.delete(oldestSessionId);
                logger.debug(`[SessionStore] Evicted session ${oldestSessionId} (FIFO). Total sessions: ${this.sessions.size}`);
            }
        }
    }

    /**
     * Clear all sessions (useful for testing)
     */
    clear(): void {
        this.sessions.clear();
        this.sessionOrder = [];
        logger.debug(`[SessionStore] Cleared all sessions`);
    }

    /**
     * Get current session count
     */
    getSize(): number {
        return this.sessions.size;
    }
}

// Use a global variable on globalThis to persist across hot reloads in development
declare global {
    var _ninaSessionStore: MemorySessionStore | undefined;
}

export const globalSessionStore = globalThis._ninaSessionStore || new MemorySessionStore(100);

// Assign back to globalThis to persist across hot reloads
if (!globalThis._ninaSessionStore) {
    globalThis._ninaSessionStore = globalSessionStore;
    logger.info(`[SessionStore] Initialized global session store`);
}
