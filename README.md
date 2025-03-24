# brocc

- browser-use
- cli login flow
- proxy endpoint for browser-use

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
