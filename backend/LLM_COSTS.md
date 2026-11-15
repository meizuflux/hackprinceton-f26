# Cost of the LLM deep analysis

Estimated cost of one `--llm` analysis (claim extraction plus the deepagents investigator and its verifier), based on the token usage the API reported for the recorded Kestrel run. Replaying a recorded cache, including `POST /demo` and uploads of an archive that has a cache file, costs nothing.

## Kestrel run (recorded 2026-11-14)

Model: `claude-sonnet-5-5` for all calls. 38 model calls: 12 for claim extraction, 26 for the investigator agent and its verifier subagent. The agent made 204 tool calls; tool calls run locally and are free.

Usage reported by the API, summed over all 38 responses:

| Token type | Tokens | Price per 1M tokens | Cost |
|---|---:|---:|---:|
| Uncached input | 18,691 | $2.00 | $0.04 |
| Prompt-cache writes (5-minute) | 173,931 | $2.50 | $0.43 |
| Prompt-cache reads | 1,096,990 | $0.20 | $0.22 |
| Output (16,365 of them reasoning) | 60,573 | $10.00 | $0.61 |
| **Total** | | | **≈ $1.30** |

By stage:
- **Claim extraction:** about $0.24. Mostly output: 12 structured-output calls, one per statement or interview.
- **Investigator and verifier:** about $1.06. The agent's conversation grows with each tool result; prompt caching bills most of that repeated context at the cache-read rate.

For comparison, the same token counts on `claude-opus-5-5` ($4 input, $20 output, $0.20 cache read, $5 cache write per 1M tokens) would cost about $2.40. A different model would not use exactly the same tokens, so treat this as a rough guide.

## What changes the cost

- **Case size:** claim extraction scales with the number of statements and interviews. The investigator's cost depends on how many steps it takes. Its limits are `max_steps` (default 40) and `max_insights` (default 5), and it stops early when it has nothing well supported to add. Kestrel used 26 agent and verifier calls.
- **Tool output size:** search results are capped at 20,000 characters per call, and they accumulate in the agent's context.
- **Re-recording:** changing prompts, tools, model settings or anything the model sees invalidates the cache. Expect roughly one run's cost each time you run `make backend-llm-record`.

## How these numbers were produced

Each response in `backend/llm_cache/<archive sha256>.jsonl` keeps the API's usage report (`response_metadata.usage`: `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens`). The table sums those fields. Prices are Anthropic first-party API list prices for Claude Sonnet 5.5 ($2 input, $10 output, $0.20 cache read per 1M tokens). Five-minute cache writes are billed at 1.25× the input price. Check current pricing before relying on these figures; this estimate is not a bill.

## Case chat (recorded 2026-11-14)

Each chat answer is a short tool loop on `claude-sonnet-5-5` with medium reasoning effort, at most 10 model calls. Recording the four Kestrel suggested questions with `make backend-chat-record` took 16 model calls. The API reported 63,576 uncached input tokens and 5,016 output tokens, about **$0.18** in total, or roughly $0.05 per answer. No prompt caching applied.

Replayed answers, including the recorded suggested questions, cost nothing. Each new free-typed question is billed at about the same rate; a long question can take up to 10 calls.
