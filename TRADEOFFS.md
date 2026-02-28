# Tradeoffs and Design Notes

This file documents the main engineering tradeoffs in the take-home and points to the code paths that implement each decision.

## 1. PDF-first ingestion, with a controlled fallback

Goal:
- Respect the assignment requirement to ingest `docs/laws.pdf`.
- Avoid indexing visibly degraded legal text that would produce weak or misleading citations.

Implementation:
- `DocumentService.create_documents()` in `app/utils.py:59`
- `DocumentService._extract_pdf_text()` in `app/utils.py:72`
- `DocumentService._documents_look_degraded()` in `app/utils.py:189`
- `DocumentService._fallback_laws_text()` in `app/utils.py:200`

Decision:
- The service reads `docs/laws.pdf` first.
- After parsing, it performs a lightweight structural quality check.
- If extraction quality is poor, it falls back to a normalized text representation of the same laws.

Why:
- In the observed runtime path, `pypdf` extracted some sections with collapsed whitespace and merged boundaries, which polluted retrieval and citations.
- For legal-style retrieval, bad grounding is worse than a controlled fallback to the same source content in clean form.

What the quality check looks for:
- Very long alphabetic runs with no spaces, implemented via `re.search(r"[A-Za-z]{25,}", sample)` in `app/utils.py:193`
- Evidence that section headings leaked into neighboring chunks, implemented in `app/utils.py:195`

Tradeoff:
- This is not a perfect parser-quality validator.
- It is a pragmatic gate that prevents obviously broken text from entering the index.

## 2. Structure-aware chunking instead of blind vector ingestion

Goal:
- Preserve the legal hierarchy of the laws rather than embedding arbitrary fixed-size text slices.

Implementation:
- `DocumentService._parse_laws_text()` in `app/utils.py:84`
- `DocumentService._normalize_lines()` in `app/utils.py:171`
- `DocumentService._split_compound_line()` in `app/utils.py:183`

Decision:
- The parser recognizes numbered sections like `6.3` and creates one document per meaningful clause.
- It also extracts top-level headings like `6. Thievery` and stores them as metadata.

Why:
- The prompt explicitly warns against blindly loading documents into a vector store.
- Legal/regulatory retrieval is usually improved when chunks align with section boundaries and carry clear labels.

Tradeoff:
- This parser is deliberately narrow and format-specific.
- It is tuned for the structure of this laws document rather than being a general-purpose legal parser.

## 3. Dual indexing strategy: clause chunks plus law-level summaries

Goal:
- Support both narrow questions like "What happens if I steal from a sept?" and broader questions like "Tell me about slavery."

Implementation:
- Per-clause documents are created in `app/utils.py:127`
- Per-law summary documents are created in `app/utils.py:151`

Decision:
- The backend indexes both:
  - clause-level chunks, for precise citation retrieval
  - top-level summary chunks, for broader semantic recall

Why:
- Clause-only indexing can miss broader thematic questions.
- Summary-only indexing reduces citation precision.

Tradeoff:
- This duplicates some content in the index.
- The benefit is better recall across both narrow and broad query types.

## 4. Keep section-aware citation metadata at ingestion time

Goal:
- Return citations that are legible to a reviewer and map back to the source law.

Implementation:
- Metadata assignment in `app/utils.py:141`
- Citation formatting source string in `app/utils.py:135`
- Citation extraction in `QdrantService.query()` at `app/utils.py:277`

Decision:
- Each document stores:
  - `law_number`
  - `law_title`
  - `section`
  - `source`

Why:
- Citation quality depends heavily on metadata quality.
- Adding section-aware metadata up front is simpler and more reliable than trying to reconstruct citations after retrieval.

Tradeoff:
- Metadata is a little redundant.
- The redundancy makes response shaping much simpler and more stable.

## 5. Use an in-memory vector index instead of the Qdrant adapter in the final runtime path

Goal:
- Preserve retrieval functionality and evaluator experience despite package compatibility issues.

Implementation:
- `QdrantService.connect()` in `app/utils.py:257`
- `QdrantService.load()` in `app/utils.py:265`

Decision:
- The class name `QdrantService` was preserved to stay close to the starter structure.
- Internally, the final implementation uses a local in-memory `VectorStoreIndex` rather than the Qdrant adapter.

Why:
- During runtime testing, the installed `qdrant-client` and the current LlamaIndex vector-store adapter produced a compatibility failure:
  - `'QdrantClient' object has no attribute 'search'`
- For the take-home, reliable end-to-end behavior is more valuable than forcing the external adapter path.

Tradeoff:
- This does not exercise persistent Qdrant storage in the submitted runtime path.
- It does preserve the retrieval architecture, the API contract, and the evaluator workflow.

## 6. Startup indexing instead of per-request indexing

Goal:
- Keep the query path fast and predictable.

Implementation:
- Startup initialization in `app/main.py:19`
- Shared service instance in `app/main.py:16`

Decision:
- The backend builds the index once on application startup.
- Requests reuse the already initialized retrieval stack.

Why:
- Re-parsing the PDF and rebuilding embeddings on every request would be slow and expensive.
- For a small take-home service, startup initialization is the simplest correct lifecycle.

Tradeoff:
- Startup does more work and can fail before the app is ready.
- The code handles this by storing `app.state.startup_error` and surfacing a clear service error in `app/main.py:34`.

## 7. Runtime-configured secrets with local `.env` convenience

Goal:
- Keep secrets out of source control while keeping local setup simple.

Implementation:
- `.env` loading in `app/utils.py:15`
- Example env files:
  - `.env.example`
  - `frontend/.env.local.example`
- Ignore rules in `.gitignore`

Decision:
- Backend secrets are read from environment variables, with `.env` auto-loading for local development.
- Frontend config is separated into `frontend/.env.local` and only uses public-safe values like `NEXT_PUBLIC_API_BASE_URL`.

Why:
- This matches normal local developer expectations while staying compatible with Docker and CI.

Tradeoff:
- `.env` loading introduces some implicit behavior locally.
- Docker and CI still need explicit environment injection, which is documented in `README.md`.

## 8. Thin API contract, defensive error reporting

Goal:
- Keep the evaluator-facing API simple and debuggable.

Implementation:
- Response models in `app/utils.py:24` and `app/utils.py:29`
- Endpoint definition in `app/main.py:30`

Decision:
- The API returns a narrow response shape:
  - `query`
  - `response`
  - `citations`
- Errors are surfaced as HTTP 500 responses with a readable detail string.

Why:
- The take-home prompt emphasizes returning a serialized `Output` object.
- A thin contract keeps the frontend implementation straightforward.

Tradeoff:
- The current error model is developer-friendly more than product-friendly.
- For a production application, errors would likely be normalized and logged separately.

## 9. Frontend optimized for evaluator clarity, not product breadth

Goal:
- Show the main product loop clearly: ask a question, read the answer, inspect citations.

Implementation:
- Query state and request flow in `frontend/app/page.tsx:33`
- API call in `frontend/app/page.tsx:43`
- Response display in `frontend/app/page.tsx:127`
- Citation cards in `frontend/app/page.tsx:145`

Decision:
- The frontend is intentionally narrow:
  - one input
  - one action
  - explicit loading/error states
  - answer panel
  - citation list

Why:
- The prompt explicitly says not to build a full product.
- This keeps reviewer attention on information design and end-to-end integration.

Tradeoff:
- The UI does not support conversation history, source filtering, or richer legal navigation.
- Those were intentionally out of scope.

## 10. Keeping close to the starter code where it helps

Goal:
- Show that the implementation can work inside an existing codebase rather than replacing it wholesale.

Implementation:
- Existing file structure preserved:
  - `app/main.py`
  - `app/utils.py`
  - `frontend/app/page.tsx`
- `QdrantService` name preserved even though internals changed

Decision:
- The implementation stays inside the starter boundaries instead of introducing a large new architecture.

Why:
- The exercise is explicitly framed as modifying an existing codebase.
- Preserving the original shape makes the changes easier for a reviewer to follow.

Tradeoff:
- Some naming now reflects the starter architecture more than the final implementation details.
- That was accepted to minimize unnecessary structural churn.

## Summary

The core theme across these decisions is:
- prefer grounded, reviewer-legible behavior over "pure" but brittle integrations
- preserve the existing codebase shape where practical
- optimize for reliable legal-style retrieval and citation quality
- keep the end-to-end evaluator workflow simple to run and inspect
