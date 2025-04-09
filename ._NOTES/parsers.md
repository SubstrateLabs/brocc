- unstructured is a nice easy way to cleanup markdown that's almost there, good default
- beautifulsoup selectors + structural logging is more robust but can be hairy
- ideal is using playwright and evaluating selectors on live page (but that's slow)

## prompts

implement twitter profile and the test, following same pattern as the examples provided but none of the bespoke logic way simpler, basically the same deal using selectors and bs4, and ample debug logging and the same debug threading structure. test should just print the markdown for now (when debug enabled.) remember unstructured doesnt do markdown you have to do it yourself. implement the basic thing and ask me to run the test.

implement linkedin company people and the test, following same pattern as the examples provided but none of the bespoke logic way simpler, basically the same deal but none of the logic just straight converting unstructured to markdown, and ample debug logging and the same debug threading structure. test should just print the markdown for now (when debug enabled.) remember unstructured doesnt do markdown you have to do it yourself. don't add too much noise filtering initially as you need to see the debug logs first to know what to filter. implement the basic thing and ask me to run the test.

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
