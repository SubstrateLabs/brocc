import type { TokenData } from "./redis-token-store";
import type { NextCookieStore } from "./next-cookie-store";

/**
 * Metadata about an OAuth scope for presentation to users
 * 
 * @field description Human-readable description of what the scope allows (e.g. "View docs")
 * @field category Grouping category for the scope (e.g. "docs", "write", "admin")
 */
export interface ScopeInfo {
  description?: string | null;
  category: string;
}

/**
 * Creates an OAuth authorization URL for a provider
 * 
 * This is the first step of the OAuth flow, where the user is redirected to the provider's
 * authorization page. The function should:
 * 1. Generate a state parameter for CSRF protection
 * 2. Store this state in cookies for verification during callback
 * 3. Return a properly formatted authorization URL with all required parameters
 * 
 * Different providers may have different requirements:
 * - Some providers don't support specifying scopes in the URL (e.g. Notion)
 * - Some providers don't support specifying an account (multi-tenant support)
 * 
 * @returns A Promise resolving to the authorization URL
 */
export type CreateOAuthUrlFn = (params: {
  cookieStore: NextCookieStore;
  scopes: string[];
  account?: string | null;
}) => Promise<URL>;

/**
 * Validates an OAuth code and exchanges it for an access token
 * 
 * This is the second step of the OAuth flow, where the code returned from the provider
 * is validated and exchanged for tokens. The function should:
 * 1. Validate the state parameter against the stored cookie
 * 2. Exchange the code for access tokens
 * 3. Return token data and account information
 * 
 * @returns A Promise resolving to validation result with token data and account info
 */
export type ValidateOAuthCodeFn = (params: { code: string; cookieStore: NextCookieStore }) => Promise<ValidateOAuthCodeRes>;

/**
 * Result of validating an OAuth code, including token data and account information
 * 
 * This data will be stored in Redis with a short TTL and retrieved by the CLI.
 * The account identifier should be stable and unique for the provider.
 * 
 * @field account Provider-specific account/workspace identifier (e.g. email, team_id)
 * @extends TokenData Base token data including accessToken and optional refreshToken
 */
export interface ValidateOAuthCodeRes extends TokenData {
  account: string;
}
