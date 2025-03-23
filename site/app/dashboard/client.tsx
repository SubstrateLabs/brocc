"use client";

import { ProviderPanel } from "@/components/oauth/provider-panel";
import { Skeleton } from "@/components/ui/skeleton";
import { useConnections } from "./use-connections";
import { handleSignOut } from "./actions";
import { Button } from "@/components/ui/button";

type DashboardClientProps = {
  user: {
    id: string;
    email?: string;
    firstName?: string | null;
    lastName?: string | null;
    [key: string]: unknown;
  };
  signInUrl: string;
};

function ProviderPanelSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2].map((i) => (
        <Skeleton key={i} className="h-20 w-full max-w-md" />
      ))}
    </div>
  );
}

export function DashboardPageClient({ user }: DashboardClientProps) {
  const { connections, isLoading: isLoadingConnections, refresh: refreshData } = useConnections(user.id);

  return (
    <div className="flex flex-col gap-2 h-full flex-grow">
      {isLoadingConnections ? (
        <ProviderPanelSkeleton />
      ) : (
        connections && <ProviderPanel connections={connections} userId={user.id} onSyncComplete={refreshData} />
      )}
      <div className="">
        <form action={handleSignOut}>
          <Button variant="outline" type="submit">
            Sign out
          </Button>
        </form>
      </div>
    </div>
  );
}
