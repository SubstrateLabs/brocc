## 0.0.1

- new schema:

```sql
author->contact_name
contact_identifier
contact_metadata
participant_metadatas
embedded_at
source_type (document default, contact, conversation)
remove image_data
keywords
chunk_index
```

- rework scrape abstraction
- entrypoint is "all tabs": basic scrape, or feed scrape if available (no scroll)
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
