import { SCOPES } from "./all-scopes";
import { type OauthProvider } from "@/lib/oauth/types";

/**
 * Describe a scope for a given domain
 */
export function describeScope({ scope, domain }: { scope: string; domain: OauthProvider }): string | null {
  const record = SCOPES[domain];
  const info = record[scope];
  if (!info) {
    console.warn(`No description for scope: ${scope}`);
    return null;
  }
  if (info.description) {
    return info.description;
  }
  return null;
}
