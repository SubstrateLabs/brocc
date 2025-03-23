import { type TokenStore } from "./token-store";
import { type OauthProvider } from "@/lib/oauth/types";

/**
 * Merges current scopes with requested scopes.
 * For incremental auth, we must request a superset of the current scopes.
 * e.g. https://developers.google.com/identity/protocols/oauth2/web-server#incrementalAuth
 * @returns Full scopes to request
 */
export async function incrementalAuthScopes({
  store,
  scopes,
  domain,
  userId,
  account,
}: {
  store: TokenStore;
  scopes: string[];
  domain: OauthProvider;
  userId: string;
  account?: string | null;
}): Promise<string[]> {
  const accounts = await store.getTokenAccounts({
    domain: domain,
    workosUserId: userId,
  });

  let existingScopes: string[] = [];
  if (account) {
    // If account specified, only get scopes for that account
    const match = accounts.find((acc) => acc.account === account);
    if (match?.scope) {
      existingScopes = match.scope.split(" ");
    }
  } else {
    // Otherwise combine scopes across all accounts
    existingScopes = accounts.reduce((acc: string[], account) => {
      if (account.scope) {
        acc.push(...account.scope.split(" "));
      }
      return acc;
    }, []);
  }

  const allScopes = [...new Set([...existingScopes, ...scopes])];
  return allScopes;
}
