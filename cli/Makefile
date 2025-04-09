.PHONY: format lint type-check test install clean build dev chrome test-md test-twitter

# Format code with ruff
format:
	ruff format . && ruff check --fix .

# Just run linting without fixing
lint:
	ruff check .

# Type check with pyright
type-check:
	pyright

# Run tests
test:
	pytest --log-cli-level=DEBUG

# Build frontend assets and copy to static directory
build:
	cd frontend && bun run build && cd ..
	rm -rf src/brocc_li/static/*
	cp -r frontend/dist/* src/brocc_li/static/

# Install the package in development mode
install:
	uv pip install -e ".[dev]"

# Clean up cache and build artifacts
clean:
	rm -rf .ruff_cache
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +

# build and run 
dev: build
	uv run brocc

chrome:
	uv run python -m brocc_li.chrome_tabs

test-md:
	uv run pytest src/brocc_li/tests/test_html_to_md.py -v

test-twitter-home:
	uv run pytest src/brocc_li/tests/test_twitter_home.py -v -s

test-twitter-thread:
	uv run pytest src/brocc_li/tests/test_twitter_thread.py -v -s 

test-twitter-likes:
	uv run pytest src/brocc_li/tests/test_twitter_likes.py -v -s

test-twitter: test-twitter-home test-twitter-thread test-twitter-likes

test-linkedin-feed:
	uv run pytest src/brocc_li/tests/test_linkedin_feed.py -v -s

test-linkedin-profile:
	uv run pytest src/brocc_li/tests/test_linkedin_profile.py -v -s

test-linkedin-company-posts:
	uv run pytest src/brocc_li/tests/test_linkedin_company_posts.py -v -s








