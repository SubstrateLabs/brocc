# 🥦 brocc

> Brocc: BRowser-Observer Content-Collection Liquid-Interface

Brocc is a work-in-progress tool for searching and analyzing personal data.

## Principles

1. Simple
2. Local-first
3. Auditable
4. Extensible

(see [PHILOSOPHY](._NOTES/PHILOSOPHY.md))

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
