import { handleSignOut } from "./actions";
import { Button } from "@/components/button";

export default async function Home() {
  return (
    <main className="flex flex-col h-full">
      <div className="flex-1" />
      <div className="flex justify-end p-4">
        <form action={handleSignOut}>
          <Button variant="small" type="submit">
            Sign out
          </Button>
        </form>
      </div>
    </main>
  );
}
