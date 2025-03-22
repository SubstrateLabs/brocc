import { drizzle } from "drizzle-orm/neon-http";
import { neon } from "@neondatabase/serverless";
import { getEnvVar } from "@/lib/get-env-var";
import { users } from "./schema/users";
import { apiKeys } from "./schema/api-keys";

// Create a neon client
const sql = neon(getEnvVar("POSTGRES_URL"));

// Create the drizzle client with the schema
export const db = drizzle(sql, {
  schema: {
    users,
    apiKeys,
  },
});

// Export the type of the database instance
export type DB = typeof db;
