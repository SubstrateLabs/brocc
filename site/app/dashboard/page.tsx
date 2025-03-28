import { Header } from "@/components/header";
import { getSignInUrl, withAuth } from "@workos-inc/authkit-nextjs";
import { handleSignOut } from "./actions";
import { Button } from "@/components/ui/button";

export default async function Home() {
  const { user } = await withAuth({ ensureSignedIn: true });
  const signInUrl = await getSignInUrl();
  return (
    <main className="h-screen flex flex-col">
      <Header user={user ? { ...user, id: user.id } : null} signInUrl={signInUrl} />
      <div className="p-4">
        <form action={handleSignOut}>
          <Button variant="outline" type="submit">
            Sign out
          </Button>
        </form>
      </div>
    </main>
  );
}
