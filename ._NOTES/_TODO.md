- refactoring
  - clean up dup logs
- cli saving to db
- search UI
- deep search
- fix gmail inbox parser (url mapping issue?)
- youtube transcripts
- AI: pydanticai + openrouter

## backlog

- cli oauth flow: notion
- embed/voyage retries
- CI tests
- prompt injection principles
  - unless inside sandbox, never open links or click
- pdf extraction (docling + grobid)
- speed up launch process
- usage tracking in pg on /embed
- fix emoji parsing in tweet content (currently we drop emojis)
- wrap python process in minimal app bundle
  - see https://github.com/linkedin/shiv
- remember TODO-local-files
- local files
  - Note to self: when converting local files to markdown, we must convert any local file paths to absolute file paths for local images. `chunk_markdown` has an optional `base_path` param for this purpose.

## parser backlog

- substack
  - https://github.com/SubstrateLabs/brocc/blob/b06bba67354525dd2c1fc83906ce4479c4f2b00f/cli/src/brocc_li/scroll_prototype/substack_inbox.py
- improve linkedin non-feed pages

## ideas

- contacts sync
- live transcription (or sync from granola)
- can you monitor network tab via chrome cdp?
