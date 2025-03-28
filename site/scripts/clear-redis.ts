/**
 * Clear all entries in redis
 */
import { clearRedis, countRedisEntries } from "@/lib/redis";
import { createInterface } from "node:readline/promises";

async function main() {
  const rl = createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log("⚠️  WARNING: This will clear ALL entries in Redis");

  try {
    const count = await countRedisEntries();
    console.log(`📊 Current Redis database has ${count} entries`);
  } catch (error) {
    console.error("❌ Failed to count Redis entries:", error);
  }

  const answer = await rl.question("Are you sure you want to continue? (y/n): ");

  if (answer.toLowerCase() !== "y") {
    console.log("❌ Operation cancelled");
    process.exit(0);
  }

  try {
    await clearRedis();
    process.exit(0);
  } catch (error) {
    console.error("Failed to clear Redis:", error);
    process.exit(1);
  } finally {
    rl.close();
  }
}

main();
