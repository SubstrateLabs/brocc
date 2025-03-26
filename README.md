# brocc

- ingested_at
- twitter metadata
- unified approach for ingested_at, location, sub_location
- store in duckdb schema
  - should we handle type of file? is that in the url?

```sql
CREATE TABLE documents (
    id VARCHAR PRIMARY KEY,                  -- Generated unique ID (URL hash)
    url VARCHAR NOT NULL,                    -- Original URL
    title VARCHAR,                           -- Post title (null for tweets)
    description VARCHAR,                     -- Short summary/preview of content
    content TEXT,                            -- Main textual content with integrated media references
    author_name VARCHAR,                     -- Author's display name
    author_identifier VARCHAR,               -- Platform-specific author identifier
    timestamp TIMESTAMP,                     -- Publication timestamp
    source VARCHAR NOT NULL,                 -- 'twitter', 'substack', 'local file', etc
    source_location VARCHAR,                 -- e.g. url where extraction occurred
    metadata JSON,                           -- All platform-specific fields
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- When we scraped it
);
```

in storage, help me design a consistent duckdb sql schema and utils that create this storage duckdb file in the right appdir
i want all documents to be stored in a consisten schema in duckdb
ie url, author, content, summary

- markdown chunking
- store in lancedb with chunking approach
- cli login flow
- embedding endpoint
- contacts sync: twitter, linkedin
- transcription

## backlog

- fix emoji parsing in tweet content, autonomously?

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
