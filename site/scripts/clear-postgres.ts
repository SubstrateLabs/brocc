/**
 * Clear all neon tables (leaves schemas intact)
 */
import { createInterface } from "node:readline/promises";
import { neon } from "@neondatabase/serverless";
import { getEnvVar } from "@/lib/get-env-var";
import { users } from "../db/schema/users";
import { apiKeys } from "../db/schema/api-keys";

const schema = { users, apiKeys };

async function main() {
  const rl = createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log("⚠️  WARNING: This will DELETE ALL DATA from all tables");
  const answer = await rl.question("Are you sure you want to continue? (y/n): ");

  if (answer.toLowerCase() !== "y") {
    console.log("❌ Operation cancelled");
    process.exit(0);
  }

  try {
    console.log("🔍 Connecting to database...");
    const sql = neon(getEnvVar("POSTGRES_URL"));

    // Clear all tables in the correct order based on foreign key dependencies
    console.log("🗑️  Clearing all tables...");
    console.log("[DEBUG] Schema objects:", Object.keys(schema));

    // Order matters due to foreign key constraints
    const tableNames = ["api_keys", "users"];
    console.log("[DEBUG] Detected tables:", tableNames);
    if (tableNames.length === 0) {
      console.warn("⚠️  No tables detected in schema!");
      process.exit(1);
    }

    for (const tableName of tableNames) {
      try {
        console.log(`[DEBUG] Attempting to clear table: ${tableName}`);
        await sql('DELETE FROM "' + tableName + '"');
        console.log(`✓ Cleared table: ${tableName}`);
      } catch (err) {
        console.error(`❌ Failed to clear table ${tableName}:`, err);
        throw err;
      }
    }

    console.log("✨ All tables cleared successfully");
    process.exit(0);
  } catch (error) {
    console.error("Failed to clear tables:", error);
    process.exit(1);
  } finally {
    rl.close();
  }
}

main();
