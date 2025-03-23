import { REVOKE_FUNCTIONS } from "./all-revoke-fns";
import type { TokenStore } from "./token-store";
import { SCOPES } from "./all-scopes";
import { type OauthProvider } from "@/lib/oauth/types";

/**
 * Revoke all connections across all domains
 * @returns true if all were revoked successfully
 */
export async function revokeAllConnections({ store, userId }: { store: TokenStore; userId: string }): Promise<boolean> {
  const domains = Object.keys(SCOPES) as OauthProvider[];
  let revokedCount = 0;
  for (const domain of domains) {
    const revoked = await revokeConnections({ store, domain, userId });
    if (revoked) {
      revokedCount += 1;
    }
  }
  if (revokedCount < domains.length) {
    console.warn(`incomplete: revoked ${revokedCount} of ${domains.length} domains`);
    return false;
  }
  return true;
}

/**
 * For a given domain, revoke all connections
 * @returns true if all were revoked successfully
 */
export async function revokeConnections({
  store,
  domain,
  userId,
}: {
  store: TokenStore;
  domain: OauthProvider;
  userId: string;
}): Promise<boolean> {
  const accounts = await store.getTokenAccounts({
    domain,
    workosUserId: userId,
  });
  const revokeConnectionFn = REVOKE_FUNCTIONS[domain];
  if (!revokeConnectionFn) {
    throw Error(`No registered RevokeOAuthConnectionFn for domain: ${domain}`);
  }
  let revokedCount = 0;
  for (const account of accounts) {
    const revoked = await revokeConnectionFn({
      store,
      account: account.account,
      userId,
    });
    await store.removeTokenAccount({
      domain,
      account: account.account,
      workosUserId: userId,
    });
    if (revoked) {
      revokedCount += 1;
    }
  }
  if (revokedCount < accounts.length) {
    console.warn(`incomplete: revoked ${revokedCount} of ${accounts.length} ${domain} connections`);
    return false;
  }
  return true;
}
