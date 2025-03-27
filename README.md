# brocc

- clean up extract
- clean up logging to use logger that can be swallowed
  - cursorrules: logging
- chrome class
- rework schemas for future

```sh
  title
  description
  text_content (markdown)
  image_data (b64 image data for individual photos... maybe also screenshot each element scraped)
  author_name
  author_identifier
  participant_names
  participant_identifiers
  url (optional, not primary key)
  source
  source_location
```

- cli login flow
- rework oauth to store in cli
- markdown chunking
- investigate litellm and alternatives
- store in lancedb with chunking approach
- embedding endpoint
- contact schema design
- contacts sync: twitter, linkedin
- transcription

## backlog

- fix emoji parsing in tweet content

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
