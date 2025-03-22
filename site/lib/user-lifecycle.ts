import { users } from "../db/schema/users";
import { apiKeys } from "../db/schema/api-keys";
import { v4 as uuidv4 } from "uuid";
import { eq } from "drizzle-orm";
import type { DB } from "../db";

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
      await ensureUserResources(user.id, db);
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
    await ensureUserResources(user.id, db);

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
export async function ensureUserResources(userId: string, db: DB) {
  // Ensure user has an API key
  await ensureUserApiKey(userId, db);
}

/**
 * Ensures a user has an API key, creating one if needed
 */
async function ensureUserApiKey(userId: string, db: DB) {
  const userApiKeys = await db.select().from(apiKeys).where(eq(apiKeys.userId, userId));

  if (userApiKeys.length === 0) {
    const apiSecret = `sk_${uuidv4().replace(/-/g, "")}`;
    await db.insert(apiKeys).values({
      userId: userId,
      secret: apiSecret,
    });
  }
}
