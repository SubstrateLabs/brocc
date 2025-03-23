/**
 * https://arcticjs.dev/providers/google
 */
import { Google, generateState, generateCodeVerifier, decodeIdToken } from "arctic";
import { google } from "googleapis";
import type { OAuth2Client } from "google-auth-library";
import { incrementalAuthScopes } from "../incremental-auth";
import type {
  TestOAuthConnectionFn,
  CreateOAuthUrlFn,
  ValidateOAuthCodeFn,
  RevokeOAuthConnectionFn,
} from "../provider-interface";
import type { TokenStore } from "../token-store";
import { oauthRedirectUri } from "../oauth-urls";
import { type OauthProvider } from "@/lib/oauth/types";
import { getEnvVar } from "@/lib/get-env-var";

const DOMAIN: OauthProvider = "google";
const CLIENT_ID = getEnvVar("GOOGLE_OAUTH_CLIENT_ID");
const CLIENT_SECRET = getEnvVar("GOOGLE_OAUTH_CLIENT_SECRET");
const VERIFY_COOKIE = `oauth.${DOMAIN}.code_verifier`;

function authClient(): Google {
  const redirectUri = oauthRedirectUri({ domain: DOMAIN });
  return new Google(CLIENT_ID, CLIENT_SECRET, redirectUri);
}

async function authorizedClient({
  store,
  userId,
  account,
}: {
  store: TokenStore;
  userId: string;
  account: string;
}): Promise<OAuth2Client | null> {
  const data = await store.getTokenData({
    domain: DOMAIN,
    account: account,
    workosUserId: userId,
  });
  if (!data || !data.refreshToken) {
    console.warn(`No token data for account: ${account}`);
    return null;
  }
  const client = new google.auth.OAuth2(CLIENT_ID, CLIENT_SECRET);
  client.setCredentials({ refresh_token: data.refreshToken });
  return client;
}

export const createOAuthUrl: CreateOAuthUrlFn = async ({ tokenStore, cookieStore, userId, scopes, account }) => {
  try {
    const client = authClient();
    const fullScopes = await incrementalAuthScopes({
      store: tokenStore,
      scopes,
      domain: DOMAIN,
      userId,
      account,
    });
    const state = generateState();
    const codeVerifier = generateCodeVerifier();
    await cookieStore.setEphemeral({
      name: VERIFY_COOKIE,
      value: codeVerifier,
    });
    const url = client.createAuthorizationURL(state, codeVerifier, fullScopes);
    // get a refresh token, for offline data ingestion
    url.searchParams.set("access_type", "offline");
    // https://developers.google.com/identity/openid-connect/openid-connect#login-hint
    if (account) {
      url.searchParams.set("login_hint", account);
    }
    return url;
  } catch (error) {
    console.error(error);
    throw new Error("Failed to create auth URL");
  }
};

export const validateOAuthCode: ValidateOAuthCodeFn = async ({ code, cookieStore }) => {
  const client = authClient();
  const cookieVerifier = await cookieStore.get(VERIFY_COOKIE);
  if (!cookieVerifier) {
    throw new Error(`Missing ${VERIFY_COOKIE}`);
  }
  const tokens = await client.validateAuthorizationCode(code, cookieVerifier);
  const accessToken = tokens.accessToken();
  const accessTokenExpiresAt = tokens.accessTokenExpiresAt();
  let refreshToken = null;
  if (tokens.hasRefreshToken()) {
    refreshToken = tokens.refreshToken();
  }
  const idToken = tokens.idToken();
  const claims = decodeIdToken(idToken);
  return {
    accessToken,
    accessTokenExpiresAt: accessTokenExpiresAt.toISOString(),
    refreshToken,
    // https://developers.google.com/identity/openid-connect/openid-connect#an-id-tokens-payload
    // @ts-expect-error – see docs
    account: claims.email as string,
  };
};

export const testGoogleConnection: TestOAuthConnectionFn = async ({ store, userId, account }) => {
  const client = await authorizedClient({
    store,
    userId,
    account: account as string,
  });
  if (!client) {
    return { success: false };
  }
  try {
    const oauth2 = google.oauth2({ version: "v2", auth: client });
    const _ = await oauth2.userinfo.get();
    return { success: true };
  } catch (error) {
    console.warn(`Failed test, revoking connection: ${error}`);
    await revokeGoogleConnection({ store, account, userId });
    return { success: false };
  }
};

export const revokeGoogleConnection: RevokeOAuthConnectionFn = async ({ store, account, userId }) => {
  const client = await authorizedClient({
    store,
    userId,
    account: account as string,
  });
  if (!client) {
    return false;
  }
  try {
    await client.revokeCredentials();
  } catch (error) {
    // note: this appears to successfully revoke, but throws an error
    console.warn(`error revoking credentials: ${error}`);
    // we'll explicitly remove the token and return true in this case
    await store.removeTokenAccount({
      domain: DOMAIN,
      account,
      workosUserId: userId,
    });
    return true;
  }
  await store.removeTokenAccount({
    domain: DOMAIN,
    account,
    workosUserId: userId,
  });
  return true;
};
