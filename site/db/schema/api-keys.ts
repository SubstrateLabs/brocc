import { pgTable, uuid, text, timestamp, index, boolean } from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";
import { users } from "./users";

export const KeyType = {
  FIRST_PARTY: "brocc",
  OPENROUTER: "openrouter",
} as const;

export type KeyType = (typeof KeyType)[keyof typeof KeyType];

export const apiKeys = pgTable(
  "api_keys",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    secret: text("secret").notNull().unique(),
    keyType: text("key_type").notNull().default(KeyType.FIRST_PARTY),
    name: text("name"),
    disabled: boolean("disabled").default(false),
    // https://openrouter.ai/docs/api-reference/api-keys/get-api-key
    hash: text("hash"), // OpenRouter specific field for API lookups
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  (table) => [index("apikeys_user_id_idx").on(table.userId)],
);

export const apiKeysRelations = relations(apiKeys, ({ one }) => ({
  user: one(users, {
    fields: [apiKeys.userId],
    references: [users.id],
  }),
}));
