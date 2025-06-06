# TODOs For Agent Platform

## Getting models working

- Snowflake (annoying/difficult)
- OpenAI (easy-ish, but do we investigate Responses?)
  - If we do Responses, do we need fallback non-responses client?
  - Already, some customers might be slow to support responses API...
  - Azure version of OpenAI (straightforward)
- Google Gemini (prototype pre PlatformClient exists)
- Regular Anthropic
- I'd love to see a Groq or Cerebras
- Supporting something like OpenRouter as a "platform" opens up
  a lot of other things "for free" (even if we control translation
  less than I'd like...)

### Special Platforms

- Doc intelligence like Reducto.ai
- Mistral especially their OCR-focused models
- More audio-focused like ElevenLabs

### Proxying

In general, these PlatformClients need to support having customized
base URLs, having a pre-request for token-generation (cached); having
extra body params or headers injected (for both token gen and regular request).

Proxy-related options should be uniform and applicable to all these provides.
We should assume (mostly) pass-through proxies: we don't want to be responsible
for allowing arbitrary reshaping of payloads...

There's probably some SSL/Cert stuff to think of here too that I'm forgetting.

### Testing/capabilities

We need a way to post a (candidate) model config and see if we can
connect. Ideally we have coarse and fine grained versions of this.
Coarse grained would be "with these params, can we send a very basic
test message or just at least reach the API"

Fine grained would be "can we make a tool call, a parallel tool call,
can we hit these 3 models, can we get an embeddings, etc. etc."

There's also the "what do we support, given as an API response" capabilities
aspect to think about here too.
