import { NextRequest, NextResponse } from "next/server";
import { createOAuthUrl } from "@/lib/oauth/providers/google";
import { GoogleScopes } from "@/lib/oauth/providers/google-scopes";
import { withAuth } from "@workos-inc/authkit-nextjs";
import { RedisTokenStore } from "@/lib/oauth/redis-token-store";
import { NextCookieStore } from "@/lib/oauth/next-cookie-store";

export async function POST(req: NextRequest): Promise<NextResponse> {
  const { user } = await withAuth({ ensureSignedIn: true });
  const tokenStore = new RedisTokenStore();
  const cookieStore = new NextCookieStore();

  const { account } = await req.json();
  const scopes = Object.keys(GoogleScopes);
  const url = await createOAuthUrl({
    cookieStore,
    tokenStore,
    userId: user.id,
    scopes,
    account: account,
  });
  return NextResponse.json({ url: url });
}
