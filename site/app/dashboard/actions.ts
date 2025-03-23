"use server";

import { signOut } from "@workos-inc/authkit-nextjs";
import { RedisTokenStore } from "@/lib/oauth/redis-token-store";
import { type OauthProvider } from "@/lib/oauth/types";
import { SCOPES } from "@/lib/oauth/all-scopes";
import { type TokenAccount } from "@/lib/oauth/token-store";

export async function handleSignOut() {
  await signOut();
}

const store = new RedisTokenStore();

export async function fetchConnections(userId: string) {
  const domains = Object.keys(SCOPES) as OauthProvider[];
  const connections: Record<string, TokenAccount[]> = {};

  for (const domain of domains) {
    const accounts = await store.getTokenAccounts({
      domain,
      workosUserId: userId,
    });
    if (accounts.length > 0) {
      connections[domain] = accounts;
    }
  }

  return connections;
}

export async function getAccountLabel(userId: string, domain: OauthProvider, accountId: string) {
  const accounts = await store.getTokenAccounts({
    domain,
    workosUserId: userId,
  });

  const account = accounts.find((a) => a.account === accountId);
  if (!account) {
    return accountId;
  }

  if (domain === "notion") {
    console.log("account", JSON.stringify(account, null, 2));
    if (!account.providerMetadata) {
      return account.account;
    }
    return account.providerMetadata?.workspaceName;
  } else if (domain === "slack") {
    return account.providerMetadata?.team;
  }

  return account.account;
}
