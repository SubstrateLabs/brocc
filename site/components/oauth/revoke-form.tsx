"use client";

import { Button } from "@/components/ui/button";
import { revokeConnection } from "@/lib/oauth/revoke-connection";
import { X } from "lucide-react";
import { type OauthProvider } from "@/lib/oauth/types";

export function RevokeForm({
  domain,
  account,
  userId,
}: {
  domain: OauthProvider;
  account?: string | null;
  userId: string;
}) {
  return (
    <form action={revokeConnection} className="inline">
      <input type="hidden" name="domain" value={domain} />
      {account && <input type="hidden" name="account" value={account} />}
      <input type="hidden" name="userId" value={userId} />
      <Button type="submit" size="sm" variant="outline">
        <X className="text-muted-foreground" />
        {"Remove account"}
      </Button>
    </form>
  );
}
