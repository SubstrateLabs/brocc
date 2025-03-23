import { Header } from "@/components/header";
import { getSignInUrl, withAuth } from "@workos-inc/authkit-nextjs";

export default async function Home() {
  const { user } = await withAuth();
  const signInUrl = await getSignInUrl();
  return (
    <div className="h-screen flex flex-col">
      <Header user={user ? { ...user, id: user.id } : null} signInUrl={signInUrl} />
      <main className="mx-auto max-w-7xl"></main>
    </div>
  );
}
