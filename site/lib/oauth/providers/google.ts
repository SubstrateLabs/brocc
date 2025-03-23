/**
 * https://arcticjs.dev/providers/google
 */
import { Google, generateState, generateCodeVerifier, decodeIdToken } from "arctic";
import { incrementalAuthScopes } from "../incremental-auth";
import type { CreateOAuthUrlFn, ValidateOAuthCodeFn } from "../provider-interface";
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
