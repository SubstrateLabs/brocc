# 🥦 Brocc

Brocc is a work-in-progress tool for searching and analyzing personal data. 

<details open>
<summary><h2>Principles</h2></summary>

Indexing personal data is a big responsibility. We believe this kind of software should be:

1. **Local-first**: AI features may use cloud services, but Brocc never logs or stores your data remotely. Your data is always stored on your machine.
2. **Source-visible**: You can [verify](https://github.com/SubstrateLabs/brocc) our promise to never store your data and review our architecture.
3. **Open-contribution**: Though Brocc isn't fully open-source yet (see the BSL [LICENSE](LICENSE.md)), we aspire to build a rich open-contribution community (and will explore ways to compensate top contributors).
4. **Programmable**: Our vision is to provide an interactive computational environment, with extensible foundations, malleable user interfaces, and well-designed APIs.

</details>

<details>
<summary><h2>Roadmap</h2></summary>

- `0.0.1`: Browser sense: connects to your **browser history**.
  - [ ] Read browser history up to a selected timeframe
  - [ ] Index common feeds:
    - [x] Twitter
    - [x] Substack
    - [ ] Gmail
  - [ ] Parse PDFs, including metadata for research articles
  - [ ] Chunk long articles and PDFs semantically
  - [ ] Search for "AI-related content", and get back feed items from multiple sources with an AI summary.
- `0.0.2`: API sense: connects to **web services** via OAuth.
  - [ ] OAuth connection to:
    - [ ] Notion
    - [ ] Slack
    - [ ] Discord
    - [ ] WhatsApp
    - [ ] Telegram
- `0.0.3`: File sense: connects to your **filesystem**.
  - [ ] Index local Mac applications:
    - [ ] iMessage
    - [ ] Photos
    - [ ] Notes
  - [ ] Index local files:
    - [ ] PDFs
    - [ ] Markdown files
</details>

<details open>
<summary><h2>Architecture</h2></summary>

### Local app

All local application technology is embedded, except AI inference (currently, all AI models run via cloud services). A long-term goal is to offer an option for local inference, which would enable fully on-device operation (and offline or low-data mode).

Dependencies:

- [DuckDB](https://duckdb.org): Embedded columnar database that stores document data. Because access patterns are more analytical than transactional, DuckDB's columnar storage is a good fit.
- [Polars](https://docs.pola.rs): DataFrame library, leverages Apache Arrow to avoid loading entire datasets into memory.
- [LanceDB](https://github.com/lancedb/lancedb): Embedded vector database, enables semantic search.
- [Textual](https://www.textualize.io): Terminal UI framework.
- [PydanticAI](https://ai.pydantic.dev): Agent framework.
- [OpenRouter](https://openrouter.ai/docs/quickstart): AI routing service, allows user-scoped API keys to access cloud AI models.

AI models:

- [voyage-multimodal-3](https://blog.voyageai.com/2024/11/12/voyage-multimodal-3): Embeds text and images in the same latent space, enabling multimodal search. This model must be run in the cloud until open-source alternatives improve in quality.

### Website

The web component of Brocc is intentionally minimal (following our Local-first [principle]((/?tab=readme-ov-file#principles)). We only redirect to the web app for authentication and collaboration features. AI model requests never pass through the web app.

- [Neon Postgres](https://neon.tech/docs/introduction): We store as little as possible in Postgres. What we do store: users, API keys, and collaboration settings.
- Cloudflare [R2](https://developers.cloudflare.com/r2): Free egress, cheaper than alternatives. We use it to store published data.
- [WorkOS](https://workos.com): Easier maintenance than DIY, cheaper than alternatives.
- Upstash [Redis](https://upstash.com/docs/redis/overall/getstarted): We use Redis to cache session information (with short TTL).

</details>

## FAQ

<details>
  <summary>Why is it called Brocc?</summary>
  
  The name comes from the project's acronym, BrOCCLI: Browser Observer Content Collection Liquid Interface.
</details>
