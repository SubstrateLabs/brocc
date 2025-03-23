import { NextResponse, NextRequest } from "next/server";
import { withAuth } from "@workos-inc/authkit-nextjs";
import { RedisTokenStore } from "@/lib/oauth/redis-token-store";
import { NextCookieStore } from "@/lib/oauth/next-cookie-store";
import { NotionScopes } from "@/lib/oauth/providers/notion-scopes";
import { createOAuthUrl } from "@/lib/oauth/providers/notion";

export async function POST(req: NextRequest): Promise<NextResponse> {
  const { user } = await withAuth({ ensureSignedIn: true });
  const tokenStore = new RedisTokenStore();
  const cookieStore = new NextCookieStore();

  // Get account from request body if provided
  const body = await req.json().catch(() => ({}));
  const account = body.account || null;

  const scopes = Object.keys(NotionScopes);
  const url = await createOAuthUrl({
    cookieStore,
    tokenStore,
    userId: user.id,
    scopes,
    account,
  });
  return NextResponse.json({ url: url });
}
