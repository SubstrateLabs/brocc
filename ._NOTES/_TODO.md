## 0.0.1

- pyright settings
- lancedb voyage embedding plugin (voyage.py)
  - review implementation
- generate string for embedding doc
- embed with filters

```sql
<existing fields>
chunk_index
```

- scrape all tabs

- rework scrape abstraction
- storage should _not_ update doc with same url... only update existing doc if content is identical

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
