import { Redis } from "@upstash/redis";
import { withRetry } from "@/lib/with-retry";
import { getEnvVar } from "@/lib/get-env-var";

export const AUTH_TOKEN_KEY_PREFIX = "cli:auth:token";
export const AUTH_TOKEN_TTL = 15 * 60; // 15 minutes
export const USER_CACHE_PREFIX = "user:workos";
export const USER_CACHE_TTL = 60 * 60 * 24 * 30; // 1 month
export const API_KEY_CACHE_PREFIX = "apikey:validation";
export const API_KEY_CACHE_TTL = 60 * 60 * 24 * 30; // 1 month

// Interface for auth session data stored in Redis
export interface AuthSession {
  accessToken: string;
  userId: string;
  email?: string; // Optional to maintain compatibility with existing records
  apiKey?: string; // Add API key to the auth session interface
  completed: boolean;
  createdAt: number;
}

// Interface for cached user data
export interface CachedUser {
  id: string;
  workosUserId: string;
  email: string;
  firstName: string | null;
  lastName: string | null;
  profileImage: string | null;
  createdAt: Date;
  updatedAt: Date;
  [key: string]: unknown; // Allow for additional properties
}

let _redis: Redis | null = null;

export async function getAuthToken(sessionId: string): Promise<AuthSession | null> {
  const redis = await getRedis();
  const key = buildKey(AUTH_TOKEN_KEY_PREFIX, sessionId);
  const data = await redis.get<AuthSession>(key);
  return data;
}

// For access from the callback handler
export async function storeAuthToken(
  sessionId: string,
  accessToken: string,
  userId: string,
  email?: string,
  apiKey?: string,
) {
  // Store the auth session in Redis with 15-minute expiry
  await setObject(
    buildKey(AUTH_TOKEN_KEY_PREFIX, sessionId),
    {
      accessToken,
      userId,
      email,
      apiKey, // Include API key in stored session
      completed: true,
      createdAt: Date.now(),
    } as AuthSession,
    AUTH_TOKEN_TTL,
  );
}

// User caching functions
export async function getCachedUser(workosUserId: string): Promise<CachedUser | null> {
  const cacheKey = buildKey(USER_CACHE_PREFIX, workosUserId);
  return await getObject<CachedUser>(cacheKey);
}

export async function cacheUser(workosUserId: string, userData: CachedUser): Promise<void> {
  const cacheKey = buildKey(USER_CACHE_PREFIX, workosUserId);
  await setObject(cacheKey, userData, USER_CACHE_TTL);
}

export async function getRedis() {
  if (!_redis) {
    _redis = new Redis({
      url: getEnvVar("REDIS_URL"),
      token: getEnvVar("REDIS_TOKEN"),
    });
    // Verify connection
    try {
      await _redis.ping();
    } catch (err) {
      console.error("[redis] Failed to connect:", err);
      throw err;
    }
  }
  return _redis;
}

export function buildKey(prefix: string, id: string): string {
  const key = `${prefix}:${id}`;
  return key;
}

export async function getObject<T>(key: string): Promise<T | null> {
  const redis = await getRedis();
  let data: T | null;
  try {
    data = await withRetry(
      async () => {
        const result = await redis.get<T>(key);
        return result;
      },
      2,
      250,
    );
  } catch (err) {
    console.warn("[redis] withRetry GET failed for key:", key, "err:", err);
    return null;
  }

  if (!data) {
    console.log("[getObject] no data found for key:", key);
    return null;
  }

  return data;
}

export async function setObject<T>(key: string, value: T, ttlSeconds?: number): Promise<void> {
  const redis = await getRedis();
  const jsonStr = JSON.stringify(value);
  console.log("[redis] Setting key:", key, "value:", jsonStr);
  await withRetry(
    async () => {
      if (ttlSeconds && ttlSeconds > 0) {
        // set with expiry
        await redis.set(key, jsonStr, { ex: ttlSeconds });
      } else {
        // no expiry
        await redis.set(key, jsonStr);
      }
    },
    2,
    250,
  );
}

/**
 * Caches a user ID for an API key
 */
export async function cacheApiKeyUserId(apiKey: string, userId: string): Promise<void> {
  const cacheKey = buildKey(API_KEY_CACHE_PREFIX, apiKey);
  await setObject(cacheKey, userId, API_KEY_CACHE_TTL);
}

/**
 * Gets a cached user ID for an API key
 */
export async function getCachedApiKeyUserId(apiKey: string): Promise<string | null> {
  const cacheKey = buildKey(API_KEY_CACHE_PREFIX, apiKey);
  return await getObject<string>(cacheKey);
}

// Dev utils
/**
 * Counts all entries in Redis
 */
export async function countRedisEntries(): Promise<number> {
  const redis = await getRedis();
  const count = await redis.dbsize();
  return count;
}

/**
 * Clears all entries in Redis
 */
export async function clearRedis(): Promise<void> {
  const redis = await getRedis();
  await redis.flushall();
  console.log("[redis] ✨ Redis cleared successfully");
}
