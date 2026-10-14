# Stable document and roster keys

Implement stable-key findings in “A.2 third ship round: deferred findings” (4), (10), (11): numeric/string roster IDs, URL-dependent document IDs, and source-index/document-number ordering.

Own `stable_ids.py`, document persistence and affected receipts, plus narrow render/bills source-index consumers and tests. Base on 03. Coordinate shared build/persist edits with 05.

1. Establish the document's natural identity from official data. Reproduce a DIP URL rewrite for the same Drucksache. Derive identity from the stable official reference (including Wahlperiode/source distinction if necessary); treat URL as an attribute. Cover missing numbers and multiple legitimate representations without conflating unrelated documents.
2. Implement explicit replay/schema/key-contract changes needed for existing stores. Verify document junctions and `fact_sources` reference the intended rows, foreign keys remain valid, and an unchanged replay reuses the store. Explain which previously minted keys must change and why.
3. Normalize roster source IDs at the boundary so equivalent `7` and `"7"` agree. Preserve missing-ID behavior from 03. Keep `stable_key`'s canonical serialization/type semantics intact; normalize the domain input rather than globally changing the hash function.
4. Make first-day debut document-number ordering domain-aware with a stable fallback for malformed/missing numbers. Normalize agenda source indexes consistently in persistence/render/bills. Cover indexes given as integer/string and invalid forms; source JSON remains raw.

Done when URL-only changes preserve document keys and receipt identities, equivalent roster/index representations behave consistently, and tie-breaks are deterministic and correctly documented. Update frozen vectors only for deliberate domain-contract changes.
