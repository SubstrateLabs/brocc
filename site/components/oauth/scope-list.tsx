import { KeyRound } from "lucide-react";
import { SCOPES } from "@/lib/oauth/all-scopes";
import { scopeSetForDomain } from "@/lib/oauth/all-scopes";
import { type OauthProvider } from "@/lib/oauth/types";

export function ScopeList({ domain, scopes }: { domain: OauthProvider; scopes?: string[] | null }) {
  let displayScopes = scopes;
  if (!displayScopes) {
    displayScopes = Array.from(scopeSetForDomain(domain));
  }
  return (
    <div className="flex gap-2 flex-wrap">
      {displayScopes.map(
        (scope) =>
          SCOPES[domain][scope] &&
          SCOPES[domain][scope].description && (
            <span key={scope} className={`flex items-center gap-x-1 text-xs`}>
              <KeyRound size={12} className="text-muted-foreground" />
              <span>{SCOPES[domain][scope].description}</span>
            </span>
          ),
      )}
    </div>
  );
}
