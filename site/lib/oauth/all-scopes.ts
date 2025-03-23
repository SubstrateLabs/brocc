import { type ScopeInfo } from "./provider-interface";
import { NotionScopes } from "./providers/notion-scopes";
import { SlackScopes } from "./providers/slack-scopes";
import { type OauthProvider } from "@/lib/oauth/types";
import { GoogleScopes } from "./providers/google-scopes";

export const SCOPES: Record<OauthProvider, Record<string, ScopeInfo>> = {
  google: GoogleScopes,
  slack: SlackScopes,
  notion: NotionScopes,
};

export function scopeSetForDomain(domain: OauthProvider): Set<string> {
  const scopeInfo = SCOPES[domain];
  return new Set(Object.keys(scopeInfo || {}));
}
