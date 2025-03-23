"use server";

import { REVOKE_FUNCTIONS } from "../all-revoke-fns";
import { RedisTokenStore } from "../redis-token-store";
import { revalidatePath } from "next/cache";

export async function revokeConnection(formData: FormData) {
  const domain = formData.get("domain") as string;
  const account = formData.get("account") as string;
  const userId = formData.get("userId") as string;
  const revokeFn = REVOKE_FUNCTIONS[domain];
  await revokeFn({ store: new RedisTokenStore(), account, userId });
  revalidatePath("/dashboard");
}
