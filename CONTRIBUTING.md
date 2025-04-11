Very rough notes on dev setup (will flesh this out)

## Setup

```sh
cli $ make install
```

## Running the CLI

```sh
cli $ make dev
```

## Adding parsers

```sh
cli $ make chrome
```

# Publishing the CLI

```sh
# update version in __about__.py
$ hatch build
$ hatch publish -u __token__ -a $PYPI_TOKEN
```

## Running the site locally

Add a `.env` to CLI with API_URL (see `.env.EXAMPLE`)

```sh
site $ bun install
site $ bun dev
```
