import { pgTable, uuid, text, timestamp, index } from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";
import { apiKeys } from "./api-keys";

export const users = pgTable(
  "users",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    workosUserId: text("workos_user_id").notNull().unique(),
    email: text("email").notNull().unique(),
    firstName: text("first_name"),
    lastName: text("last_name"),
    profileImage: text("profile_image"),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  (table) => [index("users_email_idx").on(table.email), index("users_workos_user_id_idx").on(table.workosUserId)],
);

export const usersRelations = relations(users, ({ many }) => ({
  apiKeys: many(apiKeys),
}));
