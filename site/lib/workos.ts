import { WorkOS } from "@workos-inc/node";
import { getEnvVar } from "./get-env-var";
import { db } from "@/db";
import { getCachedUser, cacheUser, type CachedUser } from "./redis";
import { users } from "@/db/schema/users";
import { eq } from "drizzle-orm";

const workos = new WorkOS(getEnvVar("WORKOS_API_KEY"));

/**
 * Get the user for a given workos user ID
 * @param workosUserId - The workos user ID
 * @returns The user or null if not found
 */
export async function getUser(workosUserId: string): Promise<CachedUser | null> {
  const user = await getCachedUser(workosUserId);
  if (!user) {
    const dbUser = await db.query.users.findFirst({
      where: eq(users.workosUserId, workosUserId),
    });
    if (dbUser) {
      await cacheUser(workosUserId, dbUser);
      return dbUser;
    }
    return null;
  }
  return user;
}

/**
 * Counts all WorkOS users
 */
export async function countUsers(): Promise<number> {
  let hasMore = true;
  let before: string | undefined;
  let totalCount = 0;

  while (hasMore) {
    const { data, listMetadata } = await workos.userManagement.listUsers({
      before,
      limit: 100,
    });

    totalCount += data.length;
    hasMore = !!listMetadata.before;
    before = listMetadata.before;
  }

  return totalCount;
}

/**
 * Lists and deletes all WorkOS users
 */
export async function deleteUsers(): Promise<void> {
  console.log("[workos] 🔍 Listing all users...");
  let hasMore = true;
  let before: string | undefined;
  let deletedCount = 0;

  while (hasMore) {
    const { data, listMetadata } = await workos.userManagement.listUsers({
      before,
      limit: 100,
    });

    for (const user of data) {
      console.log(`[workos] 🗑️  Deleting user ${user.email}...`);
      await workos.userManagement.deleteUser(user.id);
      deletedCount++;
    }

    hasMore = !!listMetadata.before;
    before = listMetadata.before;
  }

  console.log(`[workos] ✨ Deleted ${deletedCount} users`);
}
