- unstructured is a nice easy way to cleanup markdown that's almost there, good place to start
- beautifulsoup selectors + structural logging is more robust but can be hairy
- ideal is using playwright and evaluating selectors on live page (but that's slow)

## prompts

implement linkedin_company_about.py and the test, following same pattern as linkedin_company, basically the same deal but none of the posts logic, and ample debug logging and the same debug threading structure. test should just print the markdown for now (when debug enabled.)

## twitter

- profile gets blocked (no js)
- bookmarks gets blocked (no js)

## linkedin

- using unstructured for feed parsing, too hairy
