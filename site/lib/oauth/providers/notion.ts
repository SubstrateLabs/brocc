/**
 * https://arcticjs.dev/providers/notion
 */
import { CreateOAuthUrlFn, ValidateOAuthCodeFn } from "../provider-interface";
import { Notion, generateState } from "arctic";
import type { TokenStore } from "../token-store";
import { oauthRedirectUri } from "../oauth-urls";
import { Client } from "@notionhq/client";
import { type OauthProvider } from "@/lib/oauth/types";
import { getEnvVar } from "../../get-env-var";

const DOMAIN: OauthProvider = "notion";
const CLIENT_ID = getEnvVar("NOTION_OAUTH_CLIENT_ID");
const CLIENT_SECRET = getEnvVar("NOTION_OAUTH_CLIENT_SECRET");
const VERIFY_COOKIE = `oauth.${DOMAIN}.state`;

function authClient(): Notion {
  const redirectUri = oauthRedirectUri({ domain: DOMAIN });
  return new Notion(CLIENT_ID, CLIENT_SECRET, redirectUri);
}

export async function authorizedClient({
  store,
  account,
  userId,
}: {
  store: TokenStore;
  account: string;
  userId: string;
}): Promise<Client | null> {
  const data = await store.getTokenData({
    domain: DOMAIN,
    account: account,
    workosUserId: userId,
  });
  if (!data || !data.accessToken) {
    console.warn(`No token data for user: ${userId}`);
    return null;
  }
  const client = new Client({
    auth: data.accessToken,
  });
  return client;
}

/**
 * https://developers.notion.com/docs/authorization#step-1-navigate-the-user-to-the-integrations-authorization-url
 */
export const createOAuthUrl: CreateOAuthUrlFn = async ({
  tokenStore: _tokenStore, // unused because no scopes
  cookieStore,
  userId: _userId,
  scopes: _scopes, // scopes can't be set
  account: _account, // account can't be specified
}) => {
  try {
    const client = authClient();
    const state = generateState();
    await cookieStore.setEphemeral({
      name: VERIFY_COOKIE,
      value: state,
    });
    const url = client.createAuthorizationURL(state);
    // from docs: always use user
    url.searchParams.set("owner", "user");
    return url;
  } catch (error) {
    console.error(error);
    throw new Error("Failed to create auth URL");
  }
};

/**
 * https://developers.notion.com/docs/authorization#step-1-navigate-the-user-to-the-integrations-authorization-url
 */
export const validateOAuthCode: ValidateOAuthCodeFn = async ({ code, cookieStore }) => {
  const client = authClient();
  const cookieVerifier = await cookieStore.get(VERIFY_COOKIE);
  if (!cookieVerifier) {
    throw new Error(`Missing ${VERIFY_COOKIE}`);
  }
  const tokens = await client.validateAuthorizationCode(code);
  const accessToken = tokens.accessToken();
  const tokenData = tokens.data as unknown as {
    bot_id: string;
    workspace_id: string;
    workspace_name: string;
    workspace_icon: string;
    owner: { user: { id: string } };
  };
  const botId = tokenData.bot_id;
  const workspaceId = tokenData.workspace_id;
  const workspaceName = tokenData.workspace_name;
  const workspaceIcon = tokenData.workspace_icon;
  const userId = tokenData.owner.user.id;
  return {
    accessToken,
    account: workspaceId,
    providerMetadata: {
      botId,
      workspaceName,
      workspaceIcon,
      userId,
    },
  };
};
