import { RevokeOAuthConnectionFn } from "./provider-interface";
import { revokeSlackConnection } from "./providers/slack";
import { revokeNotionConnection } from "./providers/notion";
// import { revokeGoogleConnection } from "./providers/google";

export const REVOKE_FUNCTIONS: Record<string, RevokeOAuthConnectionFn> = {
  slack: revokeSlackConnection,
  notion: revokeNotionConnection,
  // google: revokeGoogleConnection,
};
