import { NextResponse } from "next/server";
import { withAuth } from "@workos-inc/authkit-nextjs";
import { RedisTokenStore } from "@/lib/oauth/redis-token-store";
import { NextCookieStore } from "@/lib/oauth/next-cookie-store";
import { handleCallback, HandleCallbackRes } from "@/lib/oauth/handle-callback";
import { type OauthProvider, OAUTH_PROVIDERS } from "@/lib/oauth/providers/oauth-providers";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ provider: string }> }
) {
  const { provider } = await params;
  if (!OAUTH_PROVIDERS.includes(provider as OauthProvider)) {
    return new NextResponse(null, { status: 404 });
  }
  
  const { user } = await withAuth({ ensureSignedIn: true });
  const tokenStore = new RedisTokenStore();
  const cookieStore = new NextCookieStore();
  const url = new URL(request.url);
  const searchParams = url.searchParams;
  const code = searchParams.get("code") as string;
  
  const res = await handleCallback({
    domain: provider as OauthProvider,
    userId: user.id,
    tokenStore,
    cookieStore,
    code,
  });
  
  const redirectUrl = new URL("/dashboard", request.url);
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
