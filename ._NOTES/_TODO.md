- ui for chrome://settings/?search=startup
improve the ux for the fasthtml app:
1. it says Chrome manager or something twice, i don't want any titles
2. i don't want any disconnect button if we're connected, the user shouldn't be able to manually connect or disconnect
3. if chrome is running wihout the debug port,

- button to open
- clean up fastapi server
  - review best practice for variables
  - review best practice for modularity
- chrome tab tracking
- think about process cleanup edge cases
- lucide icons in fasthtml
- source / location: needs another layer 
  - chrome::<location name: twitter>::<location: url>
- field for parent doc id
- capture parent doc for threads, comments
- scrape all tabs
- rework scrape abstraction
- research latest best pdf/paper metadata tool
- pydanticai + openrouter setup
- cli oauth flow

## backlog

- faq page anchors + accordion (expand accordion based on anchor)
- usage tracking in pg on /embed
- fix emoji parsing in tweet content (currently we drop emojis)
- wrap python process in minimal app bundle
  - see https://github.com/linkedin/shiv

## ideas

- contacts sync
- live transcription (or sync from granola)
- can you monitor network tab via chrome cdp?
