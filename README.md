# 🥦 Brocc

[![PyPI - Version](https://img.shields.io/pypi/v/brocc-li.svg)](https://pypi.org/project/brocc-li)


Brocc lets you **search everything you've seen in your browser**. 

Try the beta application:

1. Install: `pipx install brocc-li`
2. Run: `brocc`

<details open>
<summary><h2>How it works</h2></summary>


</details>

<details>
<summary><h2>System design</h2></summary>

Indexing personal data is a big responsibility. We believe this kind of software should be:

1. **Local**: Your data belongs on your computer. Brocc never logs or stores your data in the cloud (however, AI features use cloud AI models).
2. **Open**: Our system design and source code are available for inspection. We welcome open-source contributions.

Our goal is to build lightweight, durable software with minimal system requirements. We carefully choose dependencies that have this quality themselves, making pragmatic exceptions.

#### Overview

1. Brocc locally ingests documents from (1) your browser, (2) OAuth-authenticated APIs, and (3) your local filesystem.
2. Documents are converted to Markdown, chunked, and stored locally in DuckDB.
3. Document chunks are embedded (remotely) and stored locally in LanceDB.

#### Local app ([/cli](https://github.com/SubstrateLabs/brocc/tree/main/cli))

- [DuckDB](https://duckdb.org): Local columnar database
- [LanceDB](https://github.com/lancedb/lancedb): Local vector database. Embeddings (for ingestion + queries) use [Voyage AI](https://www.voyageai.com/) via our [API proxy](https://github.com/SubstrateLabs/brocc/blob/main/site/app/api/embed/route.ts).
- [OpenRouter](https://openrouter.ai/docs/quickstart): AI routing. LLM API requests are always made locally from your computer, using the OpenRouter API key we provision for your account.

#### Website ([/site](https://github.com/SubstrateLabs/brocc/tree/main/site))

- [Neon Postgres](https://neon.tech/docs/introduction): Used to store users, API keys, and collaboration settings.
- [WorkOS](https://workos.com): Used for auth.
- [Upstash Redis](https://upstash.com/docs/redis/overall/getstarted): Used to cache session information.


</details>

