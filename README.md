# 🥦 Brocc

Brocc is a new way to index and explore your digital life.

Try the beta CLI:

1. Install: `pipx install brocc-li`
2. Run: `brocc`

<details open>
<summary><h2>Principles</h2></summary>

Indexing personal data is a big responsibility. We believe this kind of software should be:

1. **Local-first**: Your data belongs on your computer. Brocc never logs or stores your data remotely. AI features use cloud services.
2. **Source-visible**: You can review our system design below, and inspect the code to verify our promise to never store your data.
3. **Open-contribution**: We aspire to build a rich open-contribution community.

</details>

<details>
<summary><h2>System Design</h2></summary>

Our general preference is to build robust embedded software that can run locally with minimal system requirements. We carefully choose dependencies that have this quality themselves, making pragmatic exceptions:

1. We host a light web application, used primarily for authentication.
2. AI models run remotely, because we prefer software with minimal system requirements.

## Primary dependencies

### Local app

- [DuckDB](https://duckdb.org): Embedded columnar database that stores document data. Because access patterns are more analytical than transactional, DuckDB's columnar storage is a good fit.
- [LanceDB](https://github.com/lancedb/lancedb): Embedded vector database using [Lance](https://github.com/lancedb/lance) storage format.
- [Polars](https://docs.pola.rs): DataFrame library, leverages Apache Arrow to avoid loading entire datasets into memory.
- [Textual](https://www.textualize.io): Terminal UI framework.
- [OpenRouter](https://openrouter.ai/docs/quickstart): AI routing service, allows user-scoped API keys to access cloud LLMs. LLM API requests are made locally from your computer, using your account's OpenRouter API [key](https://github.com/SubstrateLabs/brocc/blob/main/site/lib/user-lifecycle.ts).
- Embedding API requests (for ingestion + queries) go to [Voyage AI](https://www.voyageai.com/) via our [API proxy](https://github.com/SubstrateLabs/brocc/blob/main/site/app/api/embed/route.ts).

### Website

- [Neon Postgres](https://neon.tech/docs/introduction): Used to store users, API keys, and collaboration settings.
- [WorkOS](https://workos.com): Used for auth.
- Upstash [Redis](https://upstash.com/docs/redis/overall/getstarted): Used to cache session information.
- Cloudflare [R2](https://developers.cloudflare.com/r2): Used to store published datasets.

### Ingestion

0. Everything is a document. Many ways to "read" documents.
1. Document is converted to Markdown.
2. Markdown is chunked using a heuristic that preserves section boundaries.
3. Document metadata and chunk content are stored in DuckDB. Document metadata is stored in the `docs` table, and chunks stored in `chunks`.
4. Chunked markdown is embedded multimodally (interleaved text and images).
5. Chunk embeddings are stored in LanceDB, filterable by metadata.

</details>

<details>
<summary><h2>Roadmap</h2></summary>

- **0.0.1**: Browser sense: connects to your browser history.
  - [ ] Read browser history up to a selected timeframe
  - [ ] Index common feeds:
    - [x] Twitter
    - [x] Substack
    - [ ] Gmail
  - [ ] Parse PDFs, including metadata for research articles
  - [ ] Chunk long articles and PDFs semantically
  - [ ] Search for "AI-related content", and get back feed items from multiple sources with an AI summary.
- **0.0.2**: API sense: connects to web services via OAuth.
  - [ ] OAuth connection to:
    - [ ] Notion
    - [ ] Slack
    - [ ] Discord
    - [ ] WhatsApp
    - [ ] Telegram
- **0.0.3**: File sense: connects to your filesystem.
  - [ ] Index local Mac applications:
    - [ ] iMessage
    - [ ] Photos
    - [ ] Notes
  - [ ] Index local files:
    - [ ] PDFs
    - [ ] Markdown files

</details>
