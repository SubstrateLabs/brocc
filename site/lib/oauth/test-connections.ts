import type { TokenStore } from "./token-store";
import { TEST_FUNCTIONS } from "./all-test-fns";
import { describeScope } from "./describe-scope";
import { SCOPES } from "./all-scopes";
import { type OauthProvider } from "@/lib/oauth/types";

/**
 * @field domain e.g. "google"
 * @field account e.g. "ben@substrate.run" or a unique account string
 * @field scopes e.g. ["docs.readonly"]
 * @field scopeDescriptions e.g. ["View docs"]
 */
export interface AccountConnection {
  domain: OauthProvider;
  account: string;
  scopes?: string[] | null;
  scopeDescriptions?: string[] | null;
  providerMetadata?: Record<string, unknown> | null;
  cursor?: string | null;
  lastUpdated?: string | null;
}

/**
 * Test all connections across all domains
 * @returns a map of domain -> connected account objects
 */
export async function testAllConnections({
  store,
  userId,
}: {
  store: TokenStore;
  userId: string;
}): Promise<Record<string, AccountConnection[]>> {
  const domains = Object.keys(SCOPES) as OauthProvider[];
  const res: Record<string, AccountConnection[]> = {};
  for (const domain of domains) {
    const connections = await testConnections({ store, domain, userId });
    if (connections.length > 0) {
      res[domain] = connections;
    }
  }
  return res;
}

/**
 * For a given domain, test each account's connection
 * @param domain e.g. "google"
 * @returns a list of connected account objects
 */
export async function testConnections({
  store,
  domain,
  userId,
}: {
  store: TokenStore;
  domain: OauthProvider;
  userId: string;
}): Promise<AccountConnection[]> {
  const accounts = await store.getTokenAccounts({
    domain,
    workosUserId: userId,
  });
  const responses: AccountConnection[] = [];
  const testConnectionFn = TEST_FUNCTIONS[domain];
  if (!testConnectionFn) {
    throw Error(`No registered TestOAuthConnectionFn for domain: ${domain}`);
  }
  for (const account of accounts) {
    const connRes = await testConnectionFn({
      store,
      account: account.account as string,
      userId,
    });
    const tokenData = await store.getTokenData({
      domain: domain,
      account: account.account as string,
      workosUserId: userId,
    });
    const scopes = account.scope ? account.scope.split(" ") : null;
    const descriptions = scopes
      ? scopes.map((scope: string) => describeScope({ scope, domain })).filter((desc: string | null) => desc !== null)
      : null;
    if (connRes.success) {
      let data: AccountConnection = {
        domain: domain,
        account: account.account as string,
        providerMetadata: {
          ...(tokenData?.providerMetadata || {}),
          ...(connRes.providerMetadata || {}),
        },
        cursor: account.linkCursor,
        lastUpdated: account.lastUpdated,
      };
      if (account.scope) {
        data = {
          ...data,
          scopes: scopes,
          scopeDescriptions: descriptions,
        };
      }
      if (data.providerMetadata && Object.keys(data.providerMetadata).length > 0) {
        await store.updateProviderMetadata({
          domain,
          account: account.account as string,
          workosUserId: userId,
          providerMetadata: data.providerMetadata,
        });
      }
      responses.push(data);
    }
  }
  return responses;
}
