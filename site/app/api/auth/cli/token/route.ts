import { NextRequest, NextResponse } from "next/server";
import { getAuthToken } from "@/lib/redis";

// Endpoint for CLI to poll for token
export async function GET(request: NextRequest) {
  try {
    // Get session ID from query params
    const sessionId = request.nextUrl.searchParams.get("sessionId");
    if (!sessionId) {
      return NextResponse.json({ error: "Missing sessionId parameter" }, { status: 400 });
    }
    const session = await getAuthToken(sessionId);
    if (!session) {
      return NextResponse.json({ status: "pending", message: "Authentication not completed yet" }, { status: 202 });
    }
    if (!session.completed) {
      return NextResponse.json({ status: "pending", message: "Authentication in progress" }, { status: 202 });
    }
    const result = {
      status: "complete",
      accessToken: session.accessToken,
      userId: session.userId,
      email: session.email || null,
      apiKey: session.apiKey || null,
    };
    return NextResponse.json(result);
  } catch (error) {
    console.error("Error retrieving CLI auth token:", error);
    return NextResponse.json({ error: "Failed to retrieve authentication token" }, { status: 500 });
  }
}
