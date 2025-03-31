import { handleSignOut } from "./actions";
import { Button } from "@/components/button";

export default async function Home() {
  return (
    <main className="min-h-screen flex flex-col p-4">
      <div className="flex-1">
        <form action={handleSignOut}>
          <Button variant="default" type="submit">
            Sign out
          </Button>
        </form>
      </div>
    </main>
  );
}
