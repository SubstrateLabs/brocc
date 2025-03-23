/**
 * https://arcticjs.dev/providers/slack
 */
import { CreateOAuthUrlFn, ValidateOAuthCodeFn } from "../provider-interface";
import { Slack, generateState, decodeIdToken } from "arctic";
import { incrementalAuthScopes } from "../incremental-auth";
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
