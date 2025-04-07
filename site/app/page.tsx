import Readme from "@/markdown/readme.mdx";

export default async function Home() {
  return (
    <main className="mx-auto max-w-7xl p-4 prose prose-lg">
      <Readme />
    </main>
  );
}
