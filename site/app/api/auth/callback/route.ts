import { NextRequest, NextResponse } from "next/server";
import { WorkOS } from "@workos-inc/node";
import { storeAuthToken, getCachedUser, cacheUser } from "@/lib/redis";
import { db } from "@/db";
import { users } from "@/db/schema/users";
import { apiKeys } from "@/db/schema/api-keys";
import { eq } from "drizzle-orm";
import { createUser, ensureUserResources } from "@/lib/user-lifecycle";
import { handleAuth } from "@workos-inc/authkit-nextjs";

const workos = new WorkOS(process.env.WORKOS_API_KEY || "");
const clientId = process.env.WORKOS_CLIENT_ID || "";

// Custom handler for CLI flows and user creation
async function handleCustomFlow(request: NextRequest) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");

  if (!code) {
    return NextResponse.json({ error: "Missing authorization code" }, { status: 400 });
  }

  // Check if this is a CLI-initiated auth flow
  const isCliFlow = state?.startsWith("cli:");

  // Exchange the code for an access token
  const authResponse = await workos.userManagement.authenticateWithCode({
    clientId,
    code,
  });

  // Check Redis cache first
  let existingUser = await getCachedUser(authResponse.user.id);

  // If not in cache, check the database
  if (!existingUser) {
    const dbUser = await db.query.users.findFirst({
      where: eq(users.workosUserId, authResponse.user.id),
    });

    // Cache the result if found in database
    if (dbUser) {
      existingUser = dbUser;
      await cacheUser(authResponse.user.id, dbUser);
    }
  }

  // If user doesn't exist, create them
  if (!existingUser) {
    const newUser = await createUser(
      {
        workosUserId: authResponse.user.id,
        email: authResponse.user.email,
        firstName: authResponse.user.firstName || undefined,
        lastName: authResponse.user.lastName || undefined,
        profileImage: authResponse.user.profilePictureUrl || undefined,
      },
      db,
    );
    // Cache the new user
    await cacheUser(authResponse.user.id, newUser);
    console.log(`Created new user for WorkOS ID: ${authResponse.user.id}`);
    existingUser = newUser;
  } else {
    // Ensure existing user has all required resources
    await ensureUserResources(existingUser.id, db);
  }

  // Get the user's API key for CLI flows
  let apiKey = "";
  if (isCliFlow && existingUser) {
    const userApiKeys = await db.select().from(apiKeys).where(eq(apiKeys.userId, existingUser.id));
    if (userApiKeys.length > 0) {
      apiKey = userApiKeys[0].secret;
    }
  }

  if (isCliFlow && state) {
    // Extract the session ID from the state
    const sessionId = state.replace("cli:", "");

    // Store the token and API key for the CLI to retrieve
    storeAuthToken(sessionId, authResponse.accessToken, authResponse.user.id, authResponse.user.email, apiKey);

    // Redirect to the console page
    return NextResponse.redirect(new URL("/console", url.origin));
  }

  // For non-CLI flows, redirect to home
  return NextResponse.redirect(new URL("/", url.origin));
}

export async function GET(request: NextRequest) {
  try {
    const url = new URL(request.url);
    const state = url.searchParams.get("state");

    // If this is a CLI flow, use our custom handler
    if (state?.startsWith("cli:")) {
      return handleCustomFlow(request);
    }

    // For regular web auth flows, use the AuthKit handler
    // This will handle the code exchange and session creation
    const authHandler = handleAuth({
      returnPathname: "/", // Redirect to home after successful auth
      onSuccess: async ({ user }) => {
        if (!user) return;

        // Check Redis cache first
        let existingUser = await getCachedUser(user.id);

        // If not in cache, check the database
        if (!existingUser) {
          const dbUser = await db.query.users.findFirst({
            where: eq(users.workosUserId, user.id),
          });

          // Cache the result if found in database
          if (dbUser) {
            existingUser = dbUser;
            await cacheUser(user.id, dbUser);
          }
        }

        // If user doesn't exist, create them
        if (!existingUser) {
          const newUser = await createUser(
            {
              workosUserId: user.id,
              email: user.email,
              firstName: user.firstName || undefined,
              lastName: user.lastName || undefined,
              profileImage: user.profilePictureUrl || undefined,
            },
            db,
          );
          // Cache the new user
          await cacheUser(user.id, newUser);
          console.log(`Created new user for WorkOS ID: ${user.id}`);
        } else {
          // Ensure existing user has all required resources
          await ensureUserResources(existingUser.id, db);
        }
      },
    });

    return authHandler(request);
  } catch (error) {
    console.error("Authentication error:", error);
    return NextResponse.json({ error: "Authentication failed" }, { status: 500 });
  }
}
