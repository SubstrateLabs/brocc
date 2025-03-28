"use client";

import { useSearchParams } from "next/navigation";
import RedirectPage from "@/components/oauth/redirect-page";
import { useOAuthRedirect } from "@/lib/oauth/use-oauth-redirect";
import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { type OauthProvider, OAUTH_PROVIDERS } from "@/lib/oauth/providers/oauth-providers";
import { notFound } from "next/navigation";
import { use } from "react";

function Content({ provider }: { provider: OauthProvider }) {
  const searchParams = useSearchParams();
  const account = searchParams.get("account");
  const { error } = useOAuthRedirect(provider, account);
  return <RedirectPage domain={provider} error={error} />;
}

export default function Redirect({ params }: { params: Promise<{ provider: string }> }) {
  const { provider } = use(params);
  
  if (!OAUTH_PROVIDERS.includes(provider as OauthProvider)) {
    notFound();
  }
  return (
    // https://nextjs.org/docs/messages/missing-suspense-with-csr-bailout
    <Suspense fallback={<Skeleton className="w-[100px] h-[20px] rounded-full" />}>
      <Content provider={provider as OauthProvider} />
    </Suspense>
  );
}
