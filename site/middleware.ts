/**
 * https://workos.com/docs/user-management/nextjs/2-add-authkit-to-your-app/middleware
 */
import { authkitMiddleware } from "@workos-inc/authkit-nextjs";

export default authkitMiddleware();

// https://nextjs.org/docs/pages/building-your-application/routing/middleware#matcher
export const config = {
  matcher: [
    "/",
    "/dashboard",
    "/api/auth/url/:path*", // create oauth url
    "/api/auth/callback",
    "/api/auth/callback/:path*", // validate oauth code
    "/oauth/:path*", // oauth redirect pages
  ],
};
