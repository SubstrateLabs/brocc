import { NextResponse, NextRequest } from "next/server";
import { NextCookieStore } from "@/lib/oauth/next-cookie-store";
import { type OauthProvider, OAUTH_PROVIDERS } from "@/lib/oauth/providers/oauth-providers";

// Provider-specific modules
import { createOAuthUrl as createGoogleOAuthUrl, GoogleScopes } from "@/lib/oauth/providers/google";
import { createOAuthUrl as createNotionOAuthUrl, NotionScopes } from "@/lib/oauth/providers/notion";
import { createOAuthUrl as createSlackOAuthUrl, SlackScopes } from "@/lib/oauth/providers/slack";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ provider: string }> }
): Promise<NextResponse> {
  const { provider } = await params;
  if (!OAUTH_PROVIDERS.includes(provider as OauthProvider)) {
    return new NextResponse(null, { status: 404 });
  }
  const body = await req.json().catch(() => ({}));
  const account = body.account || null;
  const cookieStore = new NextCookieStore();

  let oauthUrl;
  switch (provider) {
    case "google":
      oauthUrl = await createGoogleOAuthUrl({
        cookieStore,
        scopes: Object.keys(GoogleScopes),
        account,
      });
      break;
    case "notion":
      oauthUrl = await createNotionOAuthUrl({
        cookieStore,
        scopes: Object.keys(NotionScopes),
        account,
      });
      break;
    case "slack":
      oauthUrl = await createSlackOAuthUrl({
        cookieStore,
        scopes: Object.keys(SlackScopes),
        account,
      });
      break;
    default:
      return new NextResponse(null, { status: 404 });
  }

  // Handle URL objects or string URLs
  const url = oauthUrl instanceof URL ? oauthUrl.toString() : oauthUrl;
  return NextResponse.json({ url });
}
