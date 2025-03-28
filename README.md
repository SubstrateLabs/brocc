# 🥦 BROCCLI (brocc): BRowser Observation Content Collection Liquid Interface

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

# notes

- twitter bookmarks (300 or so) in 2 minutes
- twitter likes (thousands) in 20 minutes
  - Successfully extracted 2717 unique tweets
    Collection rate: 160.6 tweets/minute
    Time taken: 1015.4 seconds
- substack inbox (up to march 2024) in like 20 minutes

# dev

```sh
uv pip install -e . # install package in dev mode
uv run brocc # textual
```

# install

```sh
% pipx install brocc-li
... installed package brocc-li 0.0.X, installed using Python 3.Y.Z
...  These apps are now globally available
...    - brocc
% brocc
```

# publishing the cli

```sh
# update version in __about__.py
hatch build
hatch publish -u __token__ -a $PYPI_TOKEN
```
