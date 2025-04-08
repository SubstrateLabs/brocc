import Faq from "@/markdown/faq.mdx";

export default async function Docs() {
  return (
    <main className="mx-auto max-w-4xl p-4 prose">
      <Faq />
    </main>
  );
}
