# 🥦 brocc

> Brocc: BRowser-Observer Content-Collection Liquid-Interface

Brocc is a work-in-progress tool for searching and analyzing personal data.

## Principles

Indexing personal data is a big responsibility. We believe this kind of software should be:

1. **Local-first**: Your data belongs on your machine. AI features may use cloud services, but we *never log or store your data in the cloud*.
2. **Source-visible**: You can verify our promise to not store your data.
3. **Open-contribution**: Though we're not fully open-source (see [LICENSE](LICENSE.md)), we believe in the power of open-contribution software, and may compensate top contributors.
4. **Extensible and malleable**: The big vision is an interactive computational environment, built on extensible foundations with malleable interfaces.

(see [PHILOSOPHY](._NOTES/PHILOSOPHY.md) for more)

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
