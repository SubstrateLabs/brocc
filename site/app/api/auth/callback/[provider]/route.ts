import { NextResponse } from "next/server";
import { withAuth } from "@workos-inc/authkit-nextjs";
import { TokenStore } from "@/lib/oauth/token-store";
import { CookieStore } from "@/lib/oauth/cookie-store";
import { handleCallback, HandleCallbackRes } from "@/lib/oauth/handle-callback";
import { type OauthProvider, OAUTH_PROVIDERS } from "@/lib/oauth/providers/oauth-providers";
import { getUser } from "@/lib/workos";

export async function GET(request: Request, { params }: { params: Promise<{ provider: string }> }) {
  const { provider } = await params;
  if (!OAUTH_PROVIDERS.includes(provider as OauthProvider)) {
    return new NextResponse(null, { status: 404 });
  }

  const { user } = await withAuth({ ensureSignedIn: true });
  const tokenStore = new TokenStore();
  const cookieStore = new CookieStore();
  const url = new URL(request.url);
  const searchParams = url.searchParams;
  const code = searchParams.get("code") as string;

  // Get the database user from the workos user ID
  const dbUser = await getUser(user.id);
  if (!dbUser) {
    console.error(`No database user found for WorkOS user ID: ${user.id}`);
    return NextResponse.redirect(new URL("/", request.url));
  }

  const userId = dbUser.id;
  const res = await handleCallback({
    domain: provider as OauthProvider,
    userId,
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
