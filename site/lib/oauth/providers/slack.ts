/**
 * https://arcticjs.dev/providers/slack
 */
import {
  CreateOAuthUrlFn,
  ValidateOAuthCodeFn,
  TestOAuthConnectionFn,
  RevokeOAuthConnectionFn,
} from "../provider-interface";
import { Slack, generateState, decodeIdToken } from "arctic";
import { WebClient } from "@slack/web-api";
import { incrementalAuthScopes } from "../incremental-auth";
import type { TokenStore } from "../token-store";
import { oauthRedirectUri } from "@/lib/oauth/oauth-urls";
import { type OauthProvider } from "@/lib/oauth/types";
import { getEnvVar } from "@/lib/get-env-var";

const DOMAIN: OauthProvider = "slack";
const CLIENT_ID = getEnvVar("SLACK_OAUTH_CLIENT_ID");
const CLIENT_SECRET = getEnvVar("SLACK_OAUTH_CLIENT_SECRET");
const VERIFY_COOKIE = `oauth.${DOMAIN}.state`;

function authClient(): Slack {
  const redirectUri = oauthRedirectUri({ domain: DOMAIN });
  return new Slack(CLIENT_ID, CLIENT_SECRET, redirectUri);
}

async function authorizedClient({
  store,
  userId,
  account,
}: {
  store: TokenStore;
  userId: string;
  account: string;
}): Promise<WebClient | null> {
  const data = await store.getTokenData({
    domain: DOMAIN,
    account: account,
    workosUserId: userId,
  });
  if (!data || !data.accessToken) {
    console.warn(`No token data for account: ${account}`);
    return null;
  }
  const client = new WebClient(data.accessToken);
  return client;
}

/**
 * https://api.slack.com/authentication/oauth-v2#asking
 */
export const createOAuthUrl: CreateOAuthUrlFn = async ({ tokenStore, cookieStore, userId, scopes, account }) => {
  try {
    const fullScopes = await incrementalAuthScopes({
      store: tokenStore,
      scopes,
      domain: DOMAIN,
      userId,
      account,
    });

    const state = generateState();
    await cookieStore.setEphemeral({
      name: VERIFY_COOKIE,
      value: state,
    });

    // The Arctic library uses the wrong endpoint for regular API (not OIDC) scopes
    // Create the URL manually instead of using client.createAuthorizationURL
    const url = new URL("https://slack.com/oauth/v2/authorize");
    url.searchParams.set("client_id", CLIENT_ID);
    // user_scope is required for regular API scopes
    url.searchParams.set("user_scope", fullScopes.join(" "));
    url.searchParams.set("state", state);
    url.searchParams.set("redirect_uri", oauthRedirectUri({ domain: DOMAIN }));

    // https://api.slack.com/authentication/oauth-v2#team
    if (account) {
      url.searchParams.set("team", account);
    }
    return url;
  } catch (error) {
    console.error(error);
    throw new Error("Failed to create auth URL");
  }
};

/**
 * https://api.slack.com/authentication/oauth-v2#exchanging
 */
export const validateOAuthCode: ValidateOAuthCodeFn = async ({ code, cookieStore }) => {
  const client = authClient();
  const cookieVerifier = await cookieStore.get(VERIFY_COOKIE);
  if (!cookieVerifier) {
    throw new Error(`Missing ${VERIFY_COOKIE}`);
  }
  const tokens = await client.validateAuthorizationCode(code);
  // console.debug("[DEBUG] tokens", JSON.stringify(tokens, null, 2));
  // We just need the access token. By default, Slack access tokens never expire.
  // https://api.slack.com/authentication/rotation
  const accessToken = tokens.accessToken();
  const idToken = tokens.idToken();
  const claims = decodeIdToken(idToken);
  // console.debug("[DEBUG] claims", JSON.stringify(claims, null, 2));
  return {
    accessToken,
    // https://api.slack.com/authentication/sign-in-with-slack#response
    // @ts-expect-error – see docs
    account: claims["https://slack.com/team_id"],
  };
};

/**
 * https://api.slack.com/methods/auth.test
 */
export const testSlackConnection: TestOAuthConnectionFn = async ({ store, userId, account }) => {
  const client = await authorizedClient({
    store,
    userId,
    account: account as string,
  });
  if (!client) {
    return { success: false };
  }
  try {
    const res = await client.auth.test();
    return {
      success: true,
      providerMetadata: {
        url: res.url,
        team: res.team,
        user: res.user,
        team_id: res.team_id,
        user_id: res.user_id,
      },
    };
  } catch (error) {
    console.warn(`Failed test, revoking connection: ${error}`);
    await revokeSlackConnection({ store, account, userId });
    return { success: false };
  }
};

/**
 * https://api.slack.com/methods/auth.revoke
 */
export const revokeSlackConnection: RevokeOAuthConnectionFn = async ({ store, account, userId }) => {
  const client = await authorizedClient({
    store,
    userId,
    account: account as string,
  });
  if (!client) {
    return false;
  }
  try {
    await client.auth.revoke();
  } catch (error) {
    console.error(`error revoking credentials: ${error}`);
    return false;
  }
  await store.removeTokenAccount({
    domain: DOMAIN,
    account,
    workosUserId: userId,
  });
  return true;
};
