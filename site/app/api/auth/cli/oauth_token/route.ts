import { NextRequest, NextResponse } from "next/server";
import { getAuthToken } from "@/lib/redis";

// Endpoint for CLI to poll for oauth token data
export async function GET(request: NextRequest) {
    // TODO...
    return NextResponse.json({ error: "Failed to retrieve oauth token data" }, { status: 500 });
}
