import { createClient } from "redis";

const DEFAULT_REDIS_URL = "redis://localhost:6379";

type RedisClient = ReturnType<typeof createClient>;

let client: RedisClient | null = null;
let clientPromise: Promise<RedisClient> | null = null;

async function initializeClient(): Promise<RedisClient> {
    const url = process.env.REDIS_URL ?? DEFAULT_REDIS_URL;
    const redis = createClient({ url });

    redis.on("error", (err) => {
        console.error("Redis Client Error", err);
    });

    try {
        await redis.connect();
    } catch (err) {
        redis.disconnect();
        throw err;
    }

    client = redis;
    return redis;
}

export async function getRedisClient(): Promise<RedisClient> {
    if (client?.isOpen) {
        return client;
    }

    if (!clientPromise) {
        clientPromise = initializeClient().catch((err) => {
            clientPromise = null;
            throw err;
        });
    }

    return clientPromise;
}

export async function appendToStream(
    stream: string,
    message: Record<string, string>,
): Promise<string> {
    const redis = await getRedisClient();
    return redis.xAdd(stream, "*", message);
}

export async function disconnectRedis(): Promise<void> {
    if (client?.isOpen) {
        await client.quit();
    }

    client = null;
    clientPromise = null;
}