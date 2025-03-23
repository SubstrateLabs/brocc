import type { TokenStore, TokenData } from "./token-store";
import type { CookieStore } from "./cookie-store";

/**
 * @field description e.g. "View docs"
 * @field category e.g. "docs"
 */
export interface ScopeInfo {
  description?: string | null;
  category: string;
}

/** Create an OAuth URL */
export type CreateOAuthUrlFn = (params: {
  tokenStore: TokenStore;
  cookieStore: CookieStore;
  userId: string;
  scopes: string[];
  // some providers (e.g. notion) don't support specifying an account
  account?: string | null;
}) => Promise<URL>;

/** Validate an OAuth code */
export type ValidateOAuthCodeFn = (params: { code: string; cookieStore: CookieStore }) => Promise<ValidateOAuthCodeRes>;

/**
 * @field account: provider-specific account/workspace identifier (e.g. email, team_id)
 */
export interface ValidateOAuthCodeRes extends TokenData {
  account: string;
}
