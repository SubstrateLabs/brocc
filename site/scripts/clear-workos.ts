/**
 * Delete all users from WorkOS (staging)
 */
import { deleteUsers, countUsers } from "@/lib/workos";
import { createInterface } from "node:readline/promises";

async function main() {
  const rl = createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log("⚠️  WARNING: This will delete ALL WorkOS users");

  try {
    const count = await countUsers();
    console.log(`📊 Current WorkOS environment has ${count} users`);
  } catch (error) {
    console.error("❌ Failed to count users:", error);
  }

  const answer = await rl.question("Are you sure you want to continue? (y/n): ");

  if (answer.toLowerCase() !== "y") {
    console.log("❌ Operation cancelled");
    process.exit(0);
  }

  try {
    await deleteUsers();
    process.exit(0);
  } catch (error) {
    console.error("Failed to delete users:", error);
    process.exit(1);
  } finally {
    rl.close();
  }
}

main();
