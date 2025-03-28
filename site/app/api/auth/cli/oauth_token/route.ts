import { NextRequest, NextResponse } from "next/server";
import { requireApiAuth } from "@/lib/api-key-auth";
import { RedisTokenStore } from "@/lib/oauth/redis-token-store";
import { type OauthProvider } from "@/lib/oauth/providers/oauth-providers";

// Endpoint for CLI to poll for oauth token data
export async function GET(request: NextRequest) {
    try {
        // 1. Authenticate the request
        const authResult = await requireApiAuth(request);
        if (!('userId' in authResult)) {
            return authResult;  // Return error response from requireApiAuth
        }
        const userId = authResult.userId;

        // 2. Parse required parameters
        const provider = request.nextUrl.searchParams.get("provider") as OauthProvider;
        const account = request.nextUrl.searchParams.get("account");
        
        if (!provider) {
            return NextResponse.json({ error: "Missing provider parameter" }, { status: 400 });
        }
        
        if (!account) {
            return NextResponse.json({ error: "Missing account parameter" }, { status: 400 });
        }

        // 3. Get the token data from Redis
        const tokenStore = new RedisTokenStore();
        const tokenData = await tokenStore.getTokenData({
            domain: provider,
            account,
            userId,
        });

        if (!tokenData) {
            return NextResponse.json({ error: "No token data found for the specified parameters" }, { status: 404 });
        }

        // 4. Return the token data
        return NextResponse.json(tokenData);
    } catch (error) {
        console.error("Error retrieving OAuth token data:", error);
        return NextResponse.json({ error: "Failed to retrieve OAuth token data" }, { status: 500 });
    }
}
