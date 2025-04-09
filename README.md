# 🥦 Brocc

[![PyPI - Version](https://img.shields.io/pypi/v/brocc-li.svg)](https://pypi.org/project/brocc-li)

Brocc lets you **search and chat with your browsing activity**.

[Install the beta using pipx](https://brocc.li/faq#installation):

1. Install: `pipx install brocc-li`
2. Run: `brocc`

Brocc connects to Chrome and indexes every page you navigate to, creating a searchable, AI-enabled database for everything you've seen. Your data is stored locally on your computer.

<details>
<summary><h2>System design</h2></summary>

Indexing personal data is a big responsibility. We believe this kind of software should be:

1. **Local**: Your data belongs on your computer. Brocc never logs or stores your data in the cloud (however, AI features use cloud AI models).
2. **Open**: Our system design and code are [open](https://github.com/substratelabs/brocc?tab=License-1-ov-file) to the public and we welcome contributions.

#### Overview

1. Brocc locally ingests documents from (1) your browser, (2) OAuth-authenticated APIs, and (3) your local filesystem.
2. Everything is converted to [Markdown](https://commonmark.org/help) (straightforward for many webpages, but the long tail of content requires bespoke parsing: dynamic feeds, PDFs, APIs, etc). We split long content into chunks (sized to approximately 1-page of single-spaced text), and store everything locally in [DuckDB](https://duckdb.org).
3. Content is embedded (remotely via our API proxy to [Voyage AI](https://www.voyageai.com)) using a multi-modal embedding [model](https://blog.voyageai.com/2024/11/12/voyage-multimodal-3), and stored locally in [LanceDB](https://github.com/lancedb/lancedb), enabling semantic search across text-and-image content.
4. LLM API requests are always made locally from your computer, using the [OpenRouter](https://openrouter.ai/docs) API key we provision for your account.
5. Logging in is required to provision access to OpenRouter and our API proxy. Minimal data is stored in [Neon Postgres](https://neon.tech/docs), [WorkOS](https://workos.com), and [Upstash Redis](https://upstash.com/docs/redis).

</details>

#### [FAQ](https://brocc.li/faq)
