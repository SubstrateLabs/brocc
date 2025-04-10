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
	pytest -n auto --log-cli-level=DEBUG

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
	uv run pytest src/brocc_li/tests/parsers/test_twitter_home.py -v -s

test-twitter-thread:
	uv run pytest src/brocc_li/tests/parsers/test_twitter_thread.py -v -s 

test-twitter-likes:
	uv run pytest src/brocc_li/tests/parsers/test_twitter_likes.py -v -s

test-twitter-inbox:
	uv run pytest src/brocc_li/tests/parsers/test_twitter_inbox.py -v -s

test-twitter-profile:
	uv run pytest src/brocc_li/tests/parsers/test_twitter_profile.py -v -s

test-twitter-bookmarks:
	uv run pytest src/brocc_li/tests/parsers/test_twitter_bookmarks.py -v -s

test-twitter-profile-followers:
	uv run pytest src/brocc_li/tests/parsers/test_twitter_profile_followers.py -v -s

test-twitter: \
	test-twitter-home \
	test-twitter-thread \
	test-twitter-likes \
	test-twitter-inbox \
	test-twitter-profile \
	test-twitter-bookmarks \
	test-twitter-profile-followers

test-bsky-profile:
	uv run pytest src/brocc_li/tests/parsers/test_bsky_profile.py -v -s

test-bsky-followers:
	uv run pytest src/brocc_li/tests/parsers/test_bsky_followers.py -v -s

test-bsky-feed:
	uv run pytest src/brocc_li/tests/parsers/test_bsky_feed.py -v -s

test-bsky: \
	test-bsky-profile \
	test-bsky-followers \
	test-bsky-feed


test-threads-home:
	uv run pytest src/brocc_li/tests/parsers/test_threads_home.py -v -s

test-threads-activity:
	uv run pytest src/brocc_li/tests/parsers/test_threads_activity.py -v -s

test-threads: \
	test-threads-home \
	test-threads-activity

test-linkedin-feed:
	uv run pytest src/brocc_li/tests/parsers/test_linkedin_feed.py -v -s

test-linkedin-feed-v2:
	uv run pytest src/brocc_li/tests/parsers/test_linkedin_feed_v2.py -v -s

test-linkedin-company:
	uv run pytest src/brocc_li/tests/parsers/test_linkedin_company.py -v -s

test-linkedin-profile:
	uv run pytest src/brocc_li/tests/parsers/test_linkedin_profile.py -v -s

test-linkedin-company-posts:
	uv run pytest src/brocc_li/tests/parsers/test_linkedin_company_posts.py -v -s

test-linkedin-company-about:
	uv run pytest src/brocc_li/tests/parsers/test_linkedin_company_about.py -v -s

test-linkedin-company-people:
	uv run pytest src/brocc_li/tests/parsers/test_linkedin_company_people.py -v -s

test-linkedin-connections-me:
	uv run pytest src/brocc_li/tests/parsers/test_linkedin_connections_me.py -v -s

test-linkedin-messages:
	uv run pytest src/brocc_li/tests/parsers/test_linkedin_messages.py -v -s

test-linkedin-search-connections:
	uv run pytest src/brocc_li/tests/parsers/test_linkedin_search_connections.py -v -s

test-linkedin-followers:
	uv run pytest src/brocc_li/tests/parsers/test_linkedin_followers.py -v -s

test-linkedin: \
	test-linkedin-feed \
	test-linkedin-company \
	test-linkedin-profile \
	test-linkedin-company-posts \
	test-linkedin-company-about \
	test-linkedin-connections-me \
	test-linkedin-messages \
	test-linkedin-company-people \
	test-linkedin-search-connections \
	test-linkedin-followers

test-gmail:
	uv run pytest src/brocc_li/tests/parsers/test_gmail_inbox.py -v -s

test-instagram-home:
	uv run pytest src/brocc_li/tests/parsers/test_instagram_home.py -v -s

test-instagram-profile:
	uv run pytest src/brocc_li/tests/parsers/test_instagram_profile.py -v -s

test-instagram-inbox:
	uv run pytest src/brocc_li/tests/parsers/test_instagram_inbox.py -v -s

test-instagram-explore:
	uv run pytest src/brocc_li/tests/parsers/test_instagram_explore.py -v -s

test-instagram-explore-search:
	uv run pytest src/brocc_li/tests/parsers/test_instagram_explore_search.py -v -s


test-instagram-saved-collection:
	uv run pytest src/brocc_li/tests/parsers/test_instagram_saved_collection.py -v -s

test-instagram: \
	test-instagram-home \
	test-instagram-profile \
	test-instagram-inbox \
	test-instagram-explore \
	test-instagram-explore-search \
	test-instagram-saved-collection

test-substack-inbox:
	uv run pytest src/brocc_li/tests/parsers/test_substack_inbox.py -v -s

test-substack-feed:
	uv run pytest src/brocc_li/tests/parsers/test_substack_feed.py -v -s

test-substack-activity:
	uv run pytest src/brocc_li/tests/parsers/test_substack_activity.py -v -s

test-substack: \
	test-substack-inbox \
	test-substack-feed \
	test-substack-activity

test-youtube-home:
	uv run pytest src/brocc_li/tests/parsers/test_youtube_home.py -v -s

test-youtube-history:
	uv run pytest src/brocc_li/tests/parsers/test_youtube_history.py -v -s

test-youtube: \
	test-youtube-home \
	test-youtube-history

