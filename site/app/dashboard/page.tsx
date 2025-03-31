import { handleSignOut } from "./actions";
import { Button } from "@/components/ui/button";

export default async function Home() {
  return (
    <main className="h-screen flex flex-col">
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
