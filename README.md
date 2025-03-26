# brocc

- store representative samples in scrape

## backlog

- fix emoji parsing in tweet content, autonomously?
- normalize tweet + substack under shared type (maybe?)
- store in duckdb
- contacts sync: twitter, linkedin
- cli login flow

# install

```sh
% pipx install brocc-li
... installed package brocc-li 0.0.X, installed using Python 3.Y.Z
...  These apps are now globally available
...    - brocc
% brocc
```

# developing

```sh
uv run brocc
```

# publishing the cli

```sh
# update version in __about__.py
hatch build
hatch publish -u __token__ -a $PYPI_TOKEN
```

# browser-use

- sending email example: https://github.com/browser-use/browser-use/blob/main/examples/custom-functions/notification.py
- controller = Controller(exclude_actions=['open_tab', 'search_google'])
