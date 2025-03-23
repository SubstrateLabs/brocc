"use server";

import { RedisTokenStore } from "./redis-token-store";
import { revalidatePath } from "next/cache";
import { type OauthProvider } from "./types";

export async function revokeConnection(formData: FormData) {
  const domain = formData.get("domain") as string;
  const account = formData.get("account") as string;
  const userId = formData.get("userId") as string;
  const store = new RedisTokenStore();
  // for simplicity, just remove the token account, no provider-specific revoking
  await store.removeTokenAccount({
    domain: domain as OauthProvider,
    account,
    workosUserId: userId,
  });
  revalidatePath("/dashboard");
}
