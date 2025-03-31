- mdx
- cli oauth implementation
- rework scrape abstraction
- entrypoint is "all tabs": basic scrape, or feed scrape if available (no scroll)
- storage should _not_ update doc with same url... only update existing doc if content is identical
- new schema:
  author->
  contact_name
  contact_identifier
  contact_metadata
  participant_metadatas
  embedded_at
  source_type (document default, contact, conversation)
  REMOVE image
  keywords
  chunk_index

- research latest best academic paper scraping tool
- research latest markdown chunking techniques
- pydanticai + openrouter setup
- store in lancedb with chunking approach
- mdx site
- shadcn sidebar site

## backlog

- explore "reverse engineering" approach monitoring network tab
- fix emoji parsing in tweet content (currently dropped)
- contacts sync?
- live transcription?
