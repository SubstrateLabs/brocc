# dev

```sh CLI
$ cd cli
$ uv sync
$ uv pip install -e . # install package in dev mode
$ uv run brocc
```

set interpreter path to `cli/.venv/bin/python`

```sh site
$ cd site
$ bun install
$ bun dev
```

# publish CLI

```sh
# update version in __about__.py
$ hatch build
$ hatch publish -u __token__ -a $PYPI_TOKEN
```
