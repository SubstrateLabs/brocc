- new parsers for ig, threads
- delegate to parsers based on url
- test twitter following + followers
- test linkedin followers/following: https://www.linkedin.com/mynetwork/network-manager/people-follow/followers
- robust running of parsers
- handle scrolling + rescrape
- improve db update logic, if superset replace
- schema design:
  - source / location: needs another layer
    - chrome::<location name: twitter>::<location: url>
  - field for parent doc id
    - capture parent doc for threads, comments
    - is this the same as "parent url" for browser nav?
- rework prototype extract code
- simple update cli flow using pypi version
- wrap parser code in execution timeout
- CI tests

## backlog

- AI: pydanticai + openrouter
- get youtube transcripts
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
- twitter messages
- twitter followers
- linkedin followers
- linkedin messages
- linkedin company people

## ideas

- contacts sync
- live transcription (or sync from granola)
- can you monitor network tab via chrome cdp?
