import { Header } from "@/components/header";
import { getSignInUrl, withAuth } from "@workos-inc/authkit-nextjs";
import { DashboardPageClient } from "./client";

export default async function Home() {
  const { user } = await withAuth({ ensureSignedIn: true });
  const signInUrl = await getSignInUrl();
  return (
    <main className="h-screen flex flex-col">
      <Header user={user ? { ...user, id: user.id } : null} signInUrl={signInUrl} />
      <DashboardPageClient
        user={{
          ...user,
          id: user.id,
        }}
        signInUrl={signInUrl}
      />
    </main>
  );
}
