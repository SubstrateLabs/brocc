import { getProviderIcon } from "./provider-icon";
import "@/lib/string-extensions";
import { type OauthProvider } from "@/lib/oauth/types";

export default function RedirectPage({ domain, error }: { domain: OauthProvider; error?: string | null }) {
  const icon = getProviderIcon(domain);
  return (
    <div className="p-8 space-y-4">
      <div className="animate-pulse">
        <div className="flex items-center gap-x-2 text-muted-foreground">
          {icon && <div className="w-4 h-4">{icon}</div>}
          <div>{`Redirecting to ${domain.toTitleCase()}...`}</div>
        </div>
      </div>
      {error && <div className="pt-4 text-destructive">Error: {error}</div>}
    </div>
  );
}
