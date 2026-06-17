# Most AI memory projects are solving the wrong problem.

MemPalace recently reported 96.6% LongMemEval Recall@5 — zero LLMs in the retrieval path, raw text and vector search. mem0, LightRAG, letta, the whole field is competing on the same axis: *how reliably can I retrieve the right memory?*

We were asking that too, until we hit something the benchmarks don't measure.

---

## The problem with retrieval-only memory

At Digitizer we run multi-agent pipelines in production. At some point the question stopped being "can the agent find it?" and became messier:

- Agent A wrote a fact. Agent B overwrote it. Which one had authority?
- A hallucination entered memory in session 3 and was retrieved as ground truth for two weeks.
- Three agents writing to the same surface — no coordination, no record of who did what.

These aren't retrieval problems. No amount of hybrid scoring or LLM reranking fixes them. **They're governance problems.**

---

## What Notary does

Notary sits above the storage layer and handles three things:

1. **Write authority** — which agents are allowed to write where
2. **Provenance** — every fact is traceable to the agent, session, and timestamp that created it
3. **Fact lifecycle** — permanent, session-scoped, or volatile

It is not a memory store. It does not do retrieval. It governs what goes in and who can change it.

---

## Our production numbers

```
cat results/digitizer-production.json
```

```
Notary Benchmark Results
────────────────────────────────────────
  Facts analyzed:        1,393
  Governance score:      1.00
  Stability score:       1.00
  Provenance coverage:   1.00
  Authorship-known:      0.6604
────────────────────────────────────────

No violations found.
```

`results/digitizer-production.json` is a public summary of an internal production scan, not a raw memory export. We keep original authorship certainty separate from governance/provenance; unknown authorship stays unknown rather than being rewritten to make a metric look cleaner.

---

## What does your stack score?

Clone the repo and run the benchmark locally:

```bash
git clone https://github.com/Digitizers/notary
cd notary
python3 -m benchmark.runner your_memory.json
```

Input: a JSON export of your agent memory store.  
Output: governance score, stability score, provenance coverage, and a list of violations.

Try it on the included example first:

```bash
python3 -m benchmark.runner examples/sample_memory.json
```

Expected output (the sample is intentionally imperfect):

```
Governance score:   0.95
Stability score:    0.50
Provenance coverage: 0.95

Issues found:
  ! [f011] missing agent_id
  ! [f007] agent 'agent-summarizer' has no WriteAuthority — unauthorized overwrite
```

---

## What's in this repo

| Path | What it is |
|---|---|
| `notary/spec.py` | Core interfaces: `WriteAuthority`, `FactLifecycle`, `ProvenanceRecord`, `NotaryProtocol` |
| `benchmark/scoring.py` | Scoring engine |
| `benchmark/runner.py` | CLI entrypoint |
| `examples/sample_memory.json` | Synthetic agent memory (intentionally flawed) |
| `results/digitizer-production.json` | Our production benchmark results |

The implementation that powers our production stack is not in this repository. The spec and benchmark are.

---

## Memory format

Your memory export should follow this shape:

```json
{
  "facts": [
    {
      "fact_id": "f001",
      "content": "User prefers concise responses.",
      "agent_id": "agent-preferences",
      "session_id": "sess-001",
      "timestamp": "2026-05-01T09:12:00Z",
      "surface": "user_profile",
      "lifecycle": "permanent",
      "confidence": 0.95,
      "overwrite_of": null
    }
  ],
  "authorities": [
    {
      "agent_id": "agent-preferences",
      "allowed_surfaces": ["user_profile"],
      "can_overwrite": true
    }
  ]
}
```

`authorities` is optional. Without it, stability scoring assumes all agents have full write authority.

---

## MemPalace is right, and wrong

MemPalace is right that raw verbatim text can work surprisingly well for retrieval recall.

But retrieval recall assumes the memory was worth keeping.

Garbage in, garbage out — at 96.6% recall.

---

## Contact

We integrate Notary into production agent stacks.

If you scored below 0.8 and want to fix it — or if you're building a multi-agent system from scratch and want governance built in from day one — reach out.

See [CONTACT.md](CONTACT.md).

---

## License

MIT
