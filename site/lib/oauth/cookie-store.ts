import { cookies } from "next/headers";
import { getEnvVar } from "@/lib/get-env-var";

export class CookieStore {
  constructor() {}

  async setEphemeral({ name, value }: { name: string; value: string }): Promise<void> {
    const cookieStore = await cookies();
    const secureOpt = getEnvVar("NODE_ENV") === "production";
    cookieStore.set({
      name: name,
      value: value,
      maxAge: 60 * 10, // 10m
      httpOnly: true,
      path: "/",
      secure: secureOpt,
      sameSite: "lax",
    });
  }

  async get(name: string): Promise<string | null> {
    const cookieStore = await cookies();
    const cookie = cookieStore.get(name)?.value;
    if (cookie) {
      return cookie;
    }
    return null;
  }

  async delete(name: string): Promise<void> {
    const cookieStore = await cookies();
    cookieStore.delete(name);
  }
}
