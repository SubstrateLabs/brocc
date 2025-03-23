"use client";

import "@/lib/string-extensions";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { KeyRound, Plus, Settings } from "lucide-react";
import { type TokenAccount } from "@/lib/oauth/token-store";
import { RevokeForm } from "@/components/oauth/revoke-form";
import { SCOPES } from "@/lib/oauth/all-scopes";
import { cn } from "@/lib/utils";
import { getProviderIcon } from "@/components/oauth/provider-icon";
import { ScopeList } from "@/components/oauth/scope-list";
import { oauthCreatePath } from "@/lib/oauth/oauth-urls";
import { type OauthProvider } from "@/lib/oauth/types";
import { formatDistanceToNow } from "date-fns";
import { getAccountLabel } from "@/app/dashboard/actions";
import { useEffect, useState } from "react";

export function ProviderPanel({
  connections,
  userId,
}: {
  connections: Record<string, TokenAccount[]>;
  userId: string;
  onSyncComplete?: () => void;
}) {
  const domains = Object.keys(SCOPES) as OauthProvider[];
  domains.splice(domains.indexOf("google"), 1); // disable google for now

  // Format time to be compact like "17m" instead of "17 minutes ago"
  const formatCompactTime = (date: Date): string => {
    let res = formatDistanceToNow(date);
    // Convert "X minutes ago" to "Xm"
    res = res
      .replace(" minutes", "m")
      .replace(" minute", "m")
      .replace(" hours", "h")
      .replace(" hour", "h")
      .replace(" days", "d")
      .replace(" day", "d");
    return res + " ago";
  };

  const [accountLabels, setAccountLabels] = useState<Record<string, string>>({});

  useEffect(() => {
    // Load all account labels
    Object.entries(connections).forEach(([domain, accounts]) => {
      accounts.forEach(async (conn) => {
        const label = await getAccountLabel(userId, domain as OauthProvider, conn.account);
        if (typeof label === 'string') {
          const key = `${domain}:${conn.account}`;
          setAccountLabels((prev) => {
            const next = {...prev};
            next[key] = label;
            return next;
          });
        }
      });
    });
  }, [connections, userId]);

  return (
    <>
      {domains.map((domain) => {
        const accounts = connections[domain] || [];
        return (
          <div key={domain} className="group border hover:border-foreground rounded max-w-md px-2">
            <div className="py-1 flex items-center gap-x-2 justify-between">
              <div className="flex items-center gap-x-2">
                <div className="text-muted-foreground group-hover:text-foreground">{getProviderIcon(domain)}</div>
                {accounts.length === 0 && (
                  <Link href={oauthCreatePath({ domain })}>
                    <Button variant="outline" size="sm">
                      Connect
                    </Button>
                  </Link>
                )}
              </div>
              <div className="flex flex-col items-end text-muted-foreground">
                <div className="group-hover:text-foreground">{domain.toTitleCase()}</div>
              </div>
            </div>
            <div className="flex flex-col">
              {accounts.map((conn) => {
                return (
                  <div key={conn.account} className="hover:animate-border-pulse border-0 border-t">
                    <details className="group">
                      <summary
                        className={cn(
                          "px-1 py-1 flex items-center gap-x-2 justify-between cursor-pointer",
                          "list-none hover:bg-muted",
                        )}
                      >
                        <div className="flex gap-x-2 items-center">
                          <Settings
                            size={12}
                            className="text-muted-foreground group-open:text-foreground transition-transform group-open:rotate-90"
                          />
                          <span className="text-sm">
                            {accountLabels[`${domain}:${conn.account}`] || conn.account}
                          </span>
                        </div>
                        <div className="text-muted-foreground group-open:hidden text-xs">
                          {conn.lastUpdated && <span>{formatCompactTime(new Date(conn.lastUpdated))}</span>}
                        </div>
                      </summary>
                      <div className="p-2 space-y-2 bg-muted">
                        {conn.scope && <ScopeList domain={domain} scopes={conn.scope.split(" ")} />}
                        <div className="flex gap-x-2 items-center">
                          <div className="flex flex-col text-xs space-y-1">
                            {conn.lastUpdated && (
                              <>
                                <div>Last updated</div>
                                <div className="text-muted-foreground">
                                  {formatCompactTime(new Date(conn.lastUpdated))}
                                </div>
                              </>
                            )}
                          </div>
                          <Link
                            href={oauthCreatePath({
                              domain,
                              account: conn.account,
                            })}
                          >
                            <Button size="sm" variant="outline">
                              <KeyRound className="text-muted-foreground" />
                              <span>Manage permissions</span>
                            </Button>
                          </Link>
                          <RevokeForm domain={domain} account={conn.account} userId={userId} />
                        </div>
                      </div>
                    </details>
                  </div>
                );
              })}
              {accounts.length > 0 && (
                <div className="border-0 border-t hover:animate-border-pulse">
                  <Link href={`/oauth/${domain}`} className="group">
                    <div className="flex items-center gap-x-2 px-1 py-1 hover:bg-muted">
                      <Plus size={12} className="text-muted-foreground transition-colors" />
                      <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors">
                        Add account
                      </span>
                    </div>
                  </Link>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </>
  );
}
