/**
 * Delete all objects from R2 blob storage
 */
import { deleteAllObjects, listAllObjects } from "@/lib/r2";
import { createInterface } from "node:readline/promises";

async function main() {
  const rl = createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log("⚠️  WARNING: This will delete ALL objects in blob storage");

  try {
    const objects = await listAllObjects();
    console.log(`📊 Current blob storage has ${objects.length} objects`);
  } catch (error) {
    console.error("❌ Failed to list objects:", error);
  }

  const answer = await rl.question("Are you sure you want to continue? (y/n): ");

  if (answer.toLowerCase() !== "y") {
    console.log("❌ Operation cancelled");
    process.exit(0);
  }

  try {
    await deleteAllObjects();
    console.log("✨ Blob storage cleared successfully");
    process.exit(0);
  } catch (error) {
    console.error("❌ Failed to clear blob storage:", error);
    process.exit(1);
  } finally {
    rl.close();
  }
}

main();
