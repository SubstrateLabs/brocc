import { type ScopeInfo } from "../provider-interface";

/**
 * https://developers.notion.com/reference/capabilities
 * Notion scopes can only be configured in Integration settings.
 */
export const NotionScopes: Record<string, ScopeInfo> = {
  // Read content
  // Read comments on blocks and pages
  // Read user information, including email addresses
  // (unclear if this is all users in the workspace)
};
