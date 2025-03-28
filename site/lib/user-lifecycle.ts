/**
 * TODO: We only log OpenRouter key creation fails, could improve robustness here
 */
import { users } from "../db/schema/users";
import { apiKeys, KeyType } from "../db/schema/api-keys";
import { v4 as uuidv4 } from "uuid";
import { eq, and } from "drizzle-orm";
import type { DB } from "../db";
import { createKey as createOpenRouterKey } from "./openrouter";

const DEFAULT_CREDIT_DOLLARS = 5;

type CreateUserParams = {
  workosUserId: string;
  email: string;
  firstName?: string;
  lastName?: string;
  profileImage?: string;
};

/**
 * Creates a user and associated resources
 * @param params User creation parameters
 * @param db Drizzle database instance
 * @returns The created user
 */
export async function createUser(params: CreateUserParams, db: DB) {
  try {
    // Check if user already exists
    const existingUser = await db.select().from(users).where(eq(users.email, params.email)).limit(1);

    if (existingUser.length > 0) {
      const user = existingUser[0];
      // Ensure user has required resources
      await ensureUserResources(user, db);
      return user;
    }

    // 1. Create the user record
    const [user] = await db
      .insert(users)
      .values({
        workosUserId: params.workosUserId,
        email: params.email,
        firstName: params.firstName,
        lastName: params.lastName,
        profileImage: params.profileImage,
      })
      .returning();

    if (!user) {
      throw new Error("Failed to create user");
    }

    // 2. Create resources for the new user
    await ensureUserResources(user, db);

    return user;
  } catch (error) {
    // If anything fails, we try to clean up and re-throw
    console.error("Error in createUser:", error);
    throw error;
  }
}

/**
 * Ensures a user has all required resources
 */
export async function ensureUserResources(user: typeof users.$inferSelect, db: DB) {
  // Ensure user has API keys
  await ensureUserApiKey(user, db);
  await ensureOpenRouterApiKey(user, db);
}

/**
 * Ensures a user has a first-party API key, creating one if needed
 */
async function ensureUserApiKey(user: typeof users.$inferSelect, db: DB) {
  const userApiKeys = await db
    .select()
    .from(apiKeys)
    .where(and(
      eq(apiKeys.userId, user.id),
      eq(apiKeys.keyType, KeyType.FIRST_PARTY)
    ));

  if (userApiKeys.length === 0) {
    const apiSecret = `sk_${uuidv4().replace(/-/g, "")}`;
    await db.insert(apiKeys).values({
        userId: user.id,
      secret: apiSecret,
      keyType: KeyType.FIRST_PARTY,
      name: `initial-brocc-key`,
    });
  }
}

/**
 * Ensures a user has an OpenRouter API key, creating one if needed
 */
async function ensureOpenRouterApiKey(user: typeof users.$inferSelect, db: DB) {
  const openRouterKeys = await db
    .select()
    .from(apiKeys)
    .where(and(
      eq(apiKeys.userId, user.id),
      eq(apiKeys.keyType, KeyType.OPENROUTER)
    ));

  if (openRouterKeys.length === 0) {
    try {
      // Create key in OpenRouter
      const openRouterKey = await createOpenRouterKey({
        name: `${user.email}|${user.id}`,
        limit: DEFAULT_CREDIT_DOLLARS, 
      });
      
      // Store the key in our database
      if (openRouterKey && openRouterKey.key) {
        await db.insert(apiKeys).values({
          userId: user.id,
          secret: openRouterKey.key,
          keyType: KeyType.OPENROUTER,
          name: `initial-openrouter-key`,
          hash: openRouterKey.hash,
        });
      }
    } catch (error) {
      console.error("Error creating OpenRouter key:", error);
    }
  }
}

