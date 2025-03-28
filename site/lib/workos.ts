import { WorkOS } from "@workos-inc/node";
import { getEnvVar } from "./get-env-var";

const workos = new WorkOS(getEnvVar("WORKOS_API_KEY"));

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
