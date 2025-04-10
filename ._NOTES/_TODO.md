- db update logic: if mergeable, replace
- schema design:
  - source / location: needs another layer
    - chrome::<location name: twitter>::<location: url>
  - field for parent doc id
    - capture parent doc for threads, comments
    - is this the same as "parent url" for browser nav?
- simple update cli flow using pypi version
- youtube transcripts
- search UI
- AI: pydanticai + openrouter

## backlog

- CI tests
- substack parsing
- prompt injection thoughts
- pdf extraction (docling + grobid)
- cli oauth flow
- speed up launch process
- usage tracking in pg on /embed
- fix emoji parsing in tweet content (currently we drop emojis)
- wrap python process in minimal app bundle
  - see https://github.com/linkedin/shiv
- remember TODO-local-files

## parser backlog

- twitter profile (no content in md)
- twitter bookmarks (no content in md)
- twitter messages
- twitter followers
- linkedin followers
- linkedin messages
- linkedin company people

## ideas

- contacts sync
- live transcription (or sync from granola)
- can you monitor network tab via chrome cdp?
