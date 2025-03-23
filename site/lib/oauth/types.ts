export const OAUTH_PROVIDERS = ["notion", "slack", "google"] as const;
export type OauthProvider = (typeof OAUTH_PROVIDERS)[number];
