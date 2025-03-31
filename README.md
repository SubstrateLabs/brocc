# 🥦 brocc

> Brocc: BRowser-Observer Content-Collection Liquid-Interface

Brocc is a work-in-progress tool for searching and analyzing personal data.

## Principles

Indexing personal data is a big responsibility. We believe this kind of software should be:

1. **Local-first**: Your data belongs on your machine. AI features may use cloud services, but we _never log or store your data in the cloud_.
2. **Source-visible**: You can verify our promise to not store your data.
3. **Open-contribution**: Though we're not fully open-source (see [LICENSE](LICENSE.md)), we believe in the power of open-contribution software, and may compensate top contributors.
4. **Extensible and malleable**: Power users get something that feels like an interactive computational environment: extensible foundations, with malleable user interfaces, and ergonomic client APIs.

(see [PHILOSOPHY](._NOTES/PHILOSOPHY.md) for more background)

## Roadmap

- `0.0.1`: A CLI that connects to your **browser history**.
  - [ ] Read browser history up to a selected timeframe
  - [ ] Index common feeds:
    - [x] Twitter
    - [x] Substack
    - [ ] Gmail
  - [ ] Parse PDFs, including metadata for research articles
  - [ ] Chunk long articles and PDFs semantically
  - [ ] Search for "AI-related content", and get back feed items from multiple sources with an AI summary.
- `0.0.2`: A CLI that connects to **web services**.
  - [ ] OAuth connection to index:
    - [ ] Notion
    - [ ] Slack
    - [ ] Discord
    - [ ] WhatsApp
    - [ ] Telegram
- `0.0.3`: A CLI that connects to your **filesystem**.
  - [ ] Index local Mac applications
    - [ ] iMessage
    - [ ] Photos
    - [ ] Notes
  - [ ] Index local files
    - [ ] PDFs
    - [ ] Markdown files

## Architecture

### site (NextJS site)

- [Neon Postgres](https://neon.tech/docs/introduction): We store as little as possible in Postgres. What we do store: Users, API Keys, and visibility settings for published data.
  - with [Drizzle](https://orm.drizzle.team/docs/overview): simple, unobtrusive ORM.
- Cloudflare [R2](https://developers.cloudflare.com/r2): Free egress + generally cheaper than alternatives. We use it to store data that users choose to publish.
- [WorkOS](https://workos.com): Easy maintenance. More legit + cheaper than alternatives.
- Upstash [Redis](https://upstash.com/docs/redis/overall/getstarted): We use Redis to cache session information (with short TTL).

### brocc-li (Python CLI)

All local application technology is embedded, except AI inference (currently, all AI models must be run using cloud services). Our long-term goal is to offer local inference, enabling fully on-device operation (and offline or low-data mode).

Dependencies:

- [DuckDB](https://duckdb.org): Embedded columnar database that stores your document data. Because access patterns (search with filters) are analytical, not transactional, DuckDB's columnar storage is a good fit.
- [Polars](https://docs.pola.rs): DataFrame library, leverages Apache Arrow to avoid loading entire datasets into memory.
- [LanceDB](https://github.com/lancedb/lancedb): Embedded vector database to enable semantic search.
- [Textual](https://www.textualize.io): Terminal UI framework
- [PydanticAI](https://ai.pydantic.dev): Agent framework

AI services:

- [voyage-multimodal-3](https://blog.voyageai.com/2024/11/12/voyage-multimodal-3): Embeds text and images in the same latent space, enabling multimodal search. This part of the application must be run as a cloud AI model, because the best open-source alternative (CLIP) is poorer quality.
- [OpenRouter](https://openrouter.ai/docs/quickstart): AI routing service, allows provisioning user-scoped API keys to access cloud AI models.
