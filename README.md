# 🥦 Brocc

Brocc is a new way to index and explore your digital life.

Try the beta application:

1. Install: `pipx install brocc-li`
2. Run: `brocc`

<details open>
<summary><h2>How it works</h2></summary>

Your documents are scattered:

1. On your local filesystem (PDFs, photos, messages...)
2. In your browser (articles, social feeds, documentation...)
3. Available via developer APIs (Notion, Slack, Gmail...)

Brocc...

</details>

<details>
<summary><h2>Principles</h2></summary>

Indexing personal data is a big responsibility. We believe this kind of software should be:

1. **Local first**: Your data belongs on your computer. We never log or store your data in the cloud. AI features utilize cloud AI models.
2. **Open pattern language**: The system design should be legible, and the source code available. You can verify that we never log or store your data in the cloud.
3. **Open contribution**: The application itself should be malleable, programmable with code or natural language. But the source code is also malleable – we welcome contributions.

</details>

<details>
<summary><h2>System design</h2></summary>

Our goal is to build lightweight, durable software with minimal system requirements. We carefully choose dependencies that have this quality themselves, making pragmatic exceptions:

1. We host a light web application, used primarily for authentication.
2. AI models run remotely. We use a specific multi-modal embedding model.

### Primary dependencies

#### Local app ([/cli](https://github.com/SubstrateLabs/brocc/tree/main/cli))

- [DuckDB](https://duckdb.org): Embedded columnar database that stores document data. Because access patterns are more analytical than transactional, DuckDB's columnar storage is a good fit.
- [LanceDB](https://github.com/lancedb/lancedb): Embedded vector database using [Lance](https://github.com/lancedb/lance) storage format.
- [Polars](https://docs.pola.rs): DataFrame library, leverages Apache Arrow to avoid loading entire datasets into memory.
- Embeddings (for ingestion + queries) use [Voyage AI](https://www.voyageai.com/) via our [API proxy](https://github.com/SubstrateLabs/brocc/blob/main/site/app/api/embed/route.ts).
- [OpenRouter](https://openrouter.ai/docs/quickstart): AI routing. LLM API requests are made locally from your computer, using the OpenRouter API key we [provision](https://github.com/SubstrateLabs/brocc/blob/main/site/lib/user-lifecycle.ts) for your account.
- [Textual](https://www.textualize.io) TUI app manages:
  - [FastAPI](https://fastapi.tiangolo.com/) local app server
  - [FastHTML](https://fastht.ml/docs) local frontend
  - [pywebview](https://pywebview.flowrl.com/guide) and [pystray](https://github.com/moses-palmer/pystray)
  - [Playwright](https://playwright.dev/docs/intro) to read content from your browser

#### Website ([/site](https://github.com/SubstrateLabs/brocc/tree/main/site))

- [Neon Postgres](https://neon.tech/docs/introduction): Used to store users, API keys, and collaboration settings.
- [WorkOS](https://workos.com): Used for auth.
- [Upstash Redis](https://upstash.com/docs/redis/overall/getstarted): Used to cache session information.
- [Cloudflare R2](https://developers.cloudflare.com/r2): Used to store published datasets.

### Data lifecycle

0. We ingest documents from sources (1) in your browser, (2) via APIs, and (3) on your local filesystem.
1. Document is converted to Markdown.
2. Markdown is chunked using a heuristic that preserves section boundaries.
3. Document metadata and chunk content are stored in DuckDB.
4. Chunked markdown is embedded multimodally (interleaved text and images).
5. Chunk embeddings are stored in LanceDB, filterable by metadata.

</details>

<details>
<summary><h2>Roadmap</h2></summary>

- **0.0.1**: Browser sense: connects to your browser history.
  - [ ] Ingest recent browser history
  - [ ] Index feeds:
    - [x] Twitter
    - [x] Substack
    - [ ] Gmail
  - [ ] Robust PDF ingestion (online only), including article metadata
  - [ ] Basic hybrid semantic+lexical search
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
