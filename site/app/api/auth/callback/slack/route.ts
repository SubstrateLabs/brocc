import { NextResponse, NextRequest } from "next/server";
import { withAuth } from "@workos-inc/authkit-nextjs";
import { RedisTokenStore } from "@/lib/oauth/redis-token-store";
import { NextCookieStore } from "@/lib/oauth/next-cookie-store";
import { handleCallback, HandleCallbackRes } from "@/lib/oauth/handle-callback";
import { type OauthProvider } from "@/lib/oauth/types";

const DOMAIN: OauthProvider = "slack";

export async function GET(req: NextRequest): Promise<NextResponse> {
  const { user } = await withAuth({ ensureSignedIn: true });
  const tokenStore = new RedisTokenStore();
  const cookieStore = new NextCookieStore();
  const searchParams = req.nextUrl.searchParams;
  const code = searchParams.get("code") as string;
  const scope = searchParams.get("scope") as string;
  const res = await handleCallback({
    domain: DOMAIN,
    userId: user.id,
    tokenStore,
    cookieStore,
    code,
    scope,
  });
  const redirectUrl = new URL("/dashboard", req.nextUrl.toString());
  switch (res) {
    case HandleCallbackRes.Success:
      return NextResponse.redirect(redirectUrl);
    case HandleCallbackRes.InvalidOAuthParams:
      console.error("Invalid OAuth params");
      return NextResponse.redirect(redirectUrl);
    case HandleCallbackRes.UnexpectedError:
      console.error(`Unexpected error: ${searchParams.toString()}`);
      return NextResponse.redirect(redirectUrl);
  }
}
