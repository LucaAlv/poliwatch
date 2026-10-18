# A.2 performance follow-ups

Implement “Vote-member occurrence bindings: cost and use” and second-round leftovers (1), (2), after correctness and coverage land.

Own recipe representative selection, `_content_digests` and vote binding cost. This is a measured optimization task: reproduce baselines on synthetic data or a scratch reference copy before changing code.

1. Recipes r1/r3: remove repeated correlated representative selection by computing a deterministic representative once per person. Prefer an explicit content-based tie-break over hash PK order. Preserve recipe rows/figures or explain an intentional representative-label correction. Keep facts/export/compare consumers consistent; respect the published `mp_canonical` contract until a separate architecture task changes it.
2. Digests: eliminate avoidable text-PK sorting only with a documented order-independent digest that retains table/schema/row-count distinctions and detects changed/deleted/duplicated rows. Compare full rebuild cost; optimize only if worth the added code. Unchanged replay must still reuse the store and export.
3. Vote bindings: trace all readers and the exported registry contract. Occurrence continuity is used even when a page never links by that key. Prefer batching/caching equivalent binding work before dropping rows. If removal is justified, prove correction/enrichment continuity, history/page eligibility and replay behavior remain correct, and document the export contract change.

Done when measured before/after timings improve the targeted cost, behavioral equivalence is tested, and any rejected optimization has a recorded reason. Existing TODO timing claims are historical baselines, not measurements of your branch.
