import { type OauthProvider } from "@/lib/oauth/types";

export function oauthCreatePath({ domain, account }: { domain: OauthProvider; account?: string | null }): string {
  if (account) {
    return `/oauth/${domain}?account=${account}`;
  }
  return `/oauth/${domain}`;
}

function getBaseUrl(): string {
  if (process.env.VERCEL_ENV === "production") {
    return process.env.NEXT_PUBLIC_SITE_URL ?? `https://${process.env.NEXT_PUBLIC_VERCEL_URL}`;
  }
  return process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000";
}

export function oauthRedirectUri({ domain }: { domain: OauthProvider }): string {
  let baseUrl = getBaseUrl();
  if (domain === "slack") {
    // slack oauth settings doesn't allow http
    baseUrl = "https://localhost:3000";
  }
  return `${baseUrl}/api/auth/callback/${domain}`;
}
