/**
 * NOTE: currently unused, brought over from old dolly webscraping project
 */
import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { apiKeys } from "@/db/schema/api-keys";
import { eq } from "drizzle-orm";
import { getCachedApiKeyUserId, cacheApiKeyUserId } from "@/lib/redis";

/**
 * Extracts API key from Authorization header
 */
export function getApiKey(req: NextRequest): string | null {
  const authHeader = req.headers.get("Authorization");
  console.log(`🔑 [API Auth] Auth header: "${authHeader}"`);

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    console.log("❌ [API Auth] Missing or invalid Authorization header format");
    return null;
  }

  const apiKey = authHeader.substring(7); // Remove "Bearer " prefix
  console.log(`🔑 [API Auth] Extracted API key: ${apiKey.substring(0, 8)}...${apiKey.substring(apiKey.length - 5)}`);
  return apiKey;
}

/**
 * Validates an API key and returns the associated user ID
 * Uses Redis caching to reduce database hits
 * Returns null if the API key is invalid
 */
export async function validateApiKey(apiKey: string): Promise<string | null> {
  if (!apiKey) {
    console.log("❌ [API Auth] Empty API key");
    return null;
  }

  try {
    // Check cache first
    console.log(`🔍 [API Auth] Checking Redis cache for API key: ${apiKey.substring(0, 8)}...`);
    const cachedUserId = await getCachedApiKeyUserId(apiKey);

    // If found in cache, return the cached user ID
    if (cachedUserId) {
      console.log(`✅ [API Auth] Found in cache, userId: ${cachedUserId.substring(0, 8)}...`);
      return cachedUserId;
    }

    console.log(`⚠️ [API Auth] Not found in cache, querying database...`);

    // Not in cache, query the database
    const apiKeyRecords = await db.select().from(apiKeys).where(eq(apiKeys.secret, apiKey)).limit(1);

    console.log(`🔍 [API Auth] Database query returned ${apiKeyRecords.length} results`);

    const apiKeyRecord = apiKeyRecords[0];
    const userId = apiKeyRecord?.userId || null;

    // If valid, cache the result
    if (userId) {
      console.log(`✅ [API Auth] Valid API key found for userId: ${userId.substring(0, 8)}...`);
      await cacheApiKeyUserId(apiKey, userId);
    } else {
      console.log(`❌ [API Auth] No matching API key found in database`);
    }

    return userId;
  } catch (error) {
    console.error("💥 [API Auth] Error validating API key:", error);
    return null;
  }
}

/**
 * Middleware-style function to require API key authentication
 * Returns the userId if authenticated, or a NextResponse error if not
 */
export async function requireApiAuth(req: NextRequest): Promise<{ userId: string } | NextResponse> {
  console.log(`🔒 [API Auth] Authenticating request to: ${req.url}`);
  const apiKey = getApiKey(req);

  if (!apiKey) {
    console.log(`❌ [API Auth] No API key found in request`);
    return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  }

  const userId = await validateApiKey(apiKey);

  if (!userId) {
    console.log(`❌ [API Auth] Invalid API key`);
    return NextResponse.json({ error: "Invalid API key" }, { status: 401 });
  }

  console.log(`✅ [API Auth] Successfully authenticated userId: ${userId.substring(0, 8)}...`);
  return { userId };
}
