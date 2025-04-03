## 0.0.1

- unify doc + lancemodel
  vector: Any = voyage_ai.VectorField() type better
- how are we splitting multimodal markdown...
- interleaved content handling seems not supported by lance function registry?
- when storing chunks in lance, should store all the same metadata fields from doc
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
