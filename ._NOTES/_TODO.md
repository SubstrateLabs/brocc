- twitter thread
  - unified twitter utils
- twitter profile
- twitter likes (on personal profile)
- linkedin feed, profile
- twitter messages
- linkedin messages
- gmail
- instagram
- delegate to parsers based on url
- handle scrolling
- schema design:
  - source / location: needs another layer
    - chrome::<location name: twitter>::<location: url>
  - field for parent doc id
    - capture parent doc for threads, comments
    - is this the same as "parent url" for browser nav?
- rework prototype extract code
- simple update cli flow using pypi version

## backlog

- AI: pydanticai + openrouter
- pdf extraction (docling + grobid)
- cli oauth flow
- speed up launch process
- usage tracking in pg on /embed
- fix emoji parsing in tweet content (currently we drop emojis)
- wrap python process in minimal app bundle
  - see https://github.com/linkedin/shiv

## parser backlog

- twitter profile (no content in md)
- twitter bookmarks (no content in md)

## ideas

- contacts sync
- live transcription (or sync from granola)
- can you monitor network tab via chrome cdp?
