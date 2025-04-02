## 0.0.1

- when updating doc, if text content is updating, we need to delete chunks + create new ones
- storage should _not_ update doc with same url... only update existing doc if content is identical
  - also need to handle chunk updates...
- embeded_at, ingested_at (maybe remove)
- integrate lancedb voyage embedding plugin (voyage.py)
- incorporate embed_header somehow into each chunk header
- embed with filters

```sql
<existing fields>
chunk_index
```

- scrape all tabs

- rework scrape abstraction

- research latest best academic paper scraping tool
- research latest markdown chunking techniques
- pydanticai + openrouter setup
- store in lancedb with chunking approach

## 0.0.2

- cli oauth flow

## backlog

- fix emoji parsing in tweet content (currently we drop emojis)
- rob idea: "reverse engineering" approach monitoring network tab

## ideas

- contacts sync
- live transcription (or sync from granola)
