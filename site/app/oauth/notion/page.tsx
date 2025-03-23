"use client";

import { useSearchParams } from "next/navigation";
import RedirectPage from "@/components/oauth/redirect-page";
import { useOAuthRedirect } from "@/lib/oauth/hooks/use-oauth-redirect";
import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { type LinkSource } from "@/lib/types";

const DOMAIN: LinkSource = "notion";

function Content() {
  const searchParams = useSearchParams();
  const account = searchParams.get("account");
  const { error } = useOAuthRedirect(DOMAIN, account);
  return <RedirectPage domain={DOMAIN} error={error} />;
}

export default function Redirect() {
  return (
    // https://nextjs.org/docs/messages/missing-suspense-with-csr-bailout
    <Suspense
      fallback={<Skeleton className="w-[100px] h-[20px] rounded-full" />}
    >
      <Content />
    </Suspense>
  );
}
