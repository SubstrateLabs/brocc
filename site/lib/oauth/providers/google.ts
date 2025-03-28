/**
 * https://arcticjs.dev/providers/google
 * TODO: split into multiple providers for specific google services
 */
import { Google, generateState, generateCodeVerifier, decodeIdToken } from "arctic";
import type { CreateOAuthUrlFn, ValidateOAuthCodeFn } from "../provider-interface";
import { oauthRedirectUri } from "../oauth-urls";
import { type OauthProvider } from "@/lib/oauth/providers/oauth-providers";
import { getEnvVar } from "@/lib/get-env-var";
import { type ScopeInfo } from "../provider-interface";

export enum GoogleScopeCategory {
  Profile = "profile",
  Sheets = "sheets",
  Docs = "docs",
}

/**
 * https://developers.google.com/identity/protocols/oauth2/scopes
 */
export const GoogleScopes: Record<string, ScopeInfo> = {
  // Standard profile info – do not describe
  openid: { category: GoogleScopeCategory.Profile },
  profile: { category: GoogleScopeCategory.Profile },
  email: { category: GoogleScopeCategory.Profile },
  /**
   * These are "sensitive" (not "restricted") scopes.
   * Add here: https://console.cloud.google.com/auth/scopes?inv=1&invt=Abrx4g&project=broccolink-453420
   */
  "https://www.googleapis.com/auth/spreadsheets.readonly": {
    description: "View Sheets",
    category: GoogleScopeCategory.Sheets,
  },
  "https://www.googleapis.com/auth/documents.readonly": {
    description: "View Docs",
    category: GoogleScopeCategory.Docs,
  },
};


const DOMAIN: OauthProvider = "google";
const CLIENT_ID = getEnvVar("GOOGLE_OAUTH_CLIENT_ID");
const CLIENT_SECRET = getEnvVar("GOOGLE_OAUTH_CLIENT_SECRET");
const VERIFY_COOKIE = `oauth.${DOMAIN}.code_verifier`;

function authClient(): Google {
  const redirectUri = oauthRedirectUri({ domain: DOMAIN });
  return new Google(CLIENT_ID, CLIENT_SECRET, redirectUri);
}

export const createOAuthUrl: CreateOAuthUrlFn = async ({ cookieStore, scopes, account }) => {
  try {
    const client = authClient();
   const state = generateState();
    const codeVerifier = generateCodeVerifier();
    await cookieStore.setEphemeral({
      name: VERIFY_COOKIE,
      value: codeVerifier,
    });
    const url = client.createAuthorizationURL(state, codeVerifier, scopes);
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
