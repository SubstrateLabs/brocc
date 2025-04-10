## overview

- unstructured is a nice easy way to cleanup markdown that's almost there, good default
- beautifulsoup selectors + structural logging is more robust but can be hairy (see twitter, gmail, youtube)
- ideal is using playwright and evaluating selectors on live page (but that's slow so we never do that rn)
  - prev had this playwright fallback but was janky: https://github.com/SubstrateLabs/brocc/blob/d01895e5cf3907b2a69a4eb21a763b39cd6e1c73/cli/src/brocc_li/playwright_fallback.py

## backlog

- instagram saved root page doesnt work (but collection works)

## prompts

i've added another fixture, it's called \_linkedin-company-feed.html, add a new set of consts DEBUG_2, FIXTURE_2, and new test case test_parse_2, simply print the md no asserts so we can iterate

evaluate the html file (its large, use a series of greps) and implement linkedin feed v2 and the test, following same pattern as the twitter home logic provided but none of the bespoke logic way simpler, basically the same deal using selectors and bs4, and ample debug logging and the same debug threading structure. test should just print the markdown for now (when debug enabled.) your goal this round is to just find the main feed items. so inspect the html, and have ample debug logging (truncating large html blocks) to orient yourself.

implement instagram explore and the test, following same pattern as the examples provided but none of the bespoke logic way simpler, basically the same deal and similar logic converting unstructured to markdown, and ample debug logging and the same debug threading structure. test should just print the markdown for now (when debug enabled.) remember unstructured doesnt do markdown you have to do it yourself. don't add too much noise filtering initially as you need to see the debug logs first to know what to filter. implement the basic thing and ask me to run the test.

---

look at the screenshot and debug logs, improve the formatting and filtering. DO NOT hardcode anything to solve this particular case. DO NOT add any assertions to the test yet (i'll instruct you to do that once we're happy with the result).

## twitter

- md parses fine but saved html is wrong
- profile gets blocked (no js)
- bookmarks: md parses fine

## linkedin

- using unstructured for feed parsing, too hairy

## slack

- html gets blocked, need to use api
