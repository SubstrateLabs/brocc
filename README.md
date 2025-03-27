# brocc

- filter seen by source, not location (skip seen in diff locations)
- clean up extract
- kv storage option?
- markdown chunking
- store in lancedb with chunking approach
- cli login flow
- embedding endpoint
- contacts sync: twitter, linkedin
- transcription

## backlog

- fix emoji parsing in tweet content, autonomously?

# notes

```sh extracted all my twitter bookmarks in 2 minutes
Successfully extracted 338 unique tweets
Collection rate: 163.6 tweets/minute
Time taken: 124.0 seconds
```

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

# developing

# publishing the cli

```sh
# update version in __about__.py
hatch build
hatch publish -u __token__ -a $PYPI_TOKEN
```

# browser-use

- sending email example: https://github.com/browser-use/browser-use/blob/main/examples/custom-functions/notification.py
- controller = Controller(exclude_actions=['open_tab', 'search_google'])
