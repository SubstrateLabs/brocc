- (polish) add number of pages indicator in reading banner (and use regex to detect)
- pdf handling (docling)
- deepresearch: latest best pdf/paper metadata tool
- schema design:
  - source / location: needs another layer
    - chrome::<location name: twitter>::<location: url>
  - field for parent doc id
    - capture parent doc for threads, comments
    - is this the same as "parent url" for browser nav?
- rework prototype extract code
- homepage + faq page anchors + accordion (expand accordion based on anchor)

## backlog

- polish md extraction for certain pages with unstructured
- AI: pydanticai + openrouter
- simple update cli flow using pypi version
- cli oauth flow
- speed up launch process
- usage tracking in pg on /embed
- fix emoji parsing in tweet content (currently we drop emojis)
- wrap python process in minimal app bundle
  - see https://github.com/linkedin/shiv

## ideas

- contacts sync
- live transcription (or sync from granola)
- can you monitor network tab via chrome cdp?
