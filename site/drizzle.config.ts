import { defineConfig } from "drizzle-kit";
import { config } from "dotenv";
import fs from "fs";
import path from "path";

// Load from .env.local for local development (ie npx drizzle-kit push)
const envLocalPath = path.resolve(process.cwd(), ".env.local");
if (fs.existsSync(envLocalPath)) {
  console.log("Loading environment from .env.local");
  config({ path: envLocalPath });
} else {
  console.log("No .env.local found, using existing environment variables");
}

console.log("POSTGRES_URL:", process.env.POSTGRES_URL);

export default defineConfig({
  out: "./drizzle",
  schema: "./db/schema",
  dialect: "postgresql",
  dbCredentials: {
    url: process.env.POSTGRES_URL!,
  },
});
