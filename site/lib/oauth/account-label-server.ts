import { type OauthProvider } from "@/lib/oauth/types";
import { RedisTokenStore } from "./redis-token-store";

export async function accountLabelForAccount(workosUserId: string, domain: OauthProvider, accountId: string) {
  const store = new RedisTokenStore();
  const accounts = await store.getTokenAccounts({
    domain,
    workosUserId,
  });

  const account = accounts.find((a) => a.account === accountId);

  if (!account) {
    return accountId;
  }

  if (domain === "notion") {
    if (!account.providerMetadata) {
      return account.account;
    }
    return account.providerMetadata?.workspaceName;
  } else if (domain === "slack") {
    return account.providerMetadata?.team;
  }

  return account.account;
}
