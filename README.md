# brocc

- cli login flow
- rework oauth token storage to not store in redis, store in cli
- litellm + pydanticai
- markdown chunking
- investigate litellm and alternatives
- store in lancedb with chunking approach
- contacts sync: twitter, linkedin

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
