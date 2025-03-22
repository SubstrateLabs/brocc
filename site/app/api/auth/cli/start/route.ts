import { NextResponse } from "next/server";
import { WorkOS } from "@workos-inc/node";
import { v4 as uuidv4 } from "uuid";

// Initialize WorkOS client
const workos = new WorkOS(process.env.WORKOS_API_KEY || "");
const clientId = process.env.WORKOS_CLIENT_ID || "";

export async function GET() {
  try {
    // Generate a unique session ID for this CLI auth attempt
    const sessionId = uuidv4();

    // Make sure we have a valid app URL for the redirect
    // Check multiple environment variables for flexibility
    const appUrl = process.env.NEXT_PUBLIC_APP_URL || process.env.APP_URL || "http://localhost:3000";

    console.log(`Using app URL for redirect: ${appUrl}`);
    console.log("Available env vars:", {
      NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
      APP_URL: process.env.APP_URL,
    });

    // Generate the authorization URL with the session ID as state
    const authorizationUrl = workos.userManagement.getAuthorizationUrl({
      clientId,
      provider: "authkit",
      redirectUri: `${appUrl}/api/auth/callback`,
      state: `cli:${sessionId}`, // Mark this as a CLI auth flow with the unique session ID
    });

    // Return the authorization URL to the CLI
    return NextResponse.json({
      authUrl: authorizationUrl,
      sessionId,
    });
  } catch (error) {
    console.error("Error generating CLI auth URL:", error);
    return NextResponse.json({ error: "Failed to initiate authentication" }, { status: 500 });
  }
}
