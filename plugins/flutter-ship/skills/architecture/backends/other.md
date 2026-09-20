# Backends that are not FastAPI

Read this from `/architecture` step 3 for Django, Rails, Go, Node, .NET
or anything else — including an API that lives in a different repo.

Do not port the FastAPI layout onto their framework, and do not rename
their layers to match ours. Review the seams, framework-idiomatic:

| Seam | Django | Rails | Go | Nest / Express |
|---|---|---|---|---|
| **Transport** | view / serializer | controller | handler | controller |
| **Logic** | service module | service object | service | provider / service |
| **Data** | model manager / repo | model / query object | store / repo | repository |

The questions are the same in every column:

- Does the transport layer hold business rules, or just translate?
- Can the logic layer be called without an HTTP request in hand?
- Does data access sit behind one type per concept, or is it inline in
  handlers?
- Do domain errors become status codes in exactly one place?

## Review the changed files for

- **A health endpoint** the Flutter client and CI can hit. This is the
  same expectation `/fastapi-setup` sets for other backends.
- **An App Check (or equivalent attestation) verification flag**,
  defaulting off, checked in one place rather than per route.
- **Response-shape changes paired with the Dart client change** in the
  same branch — the contract rules in the skill's step 4 apply whatever
  the server is written in.
- **Lint and tests for that tree running in CI.** If the API tree has no
  job, that is a finding; the workflow belongs to whoever owns the
  service.
- **Secrets and config** read from the environment, not committed.

## When the API is in another repo

You cannot review what you cannot read. Then:

- Review only the Dart side of the contract — service, API models,
  repository transform, failure mapping.
- State in the report what you assumed the server returns, and where
  that assumption came from (an OpenAPI doc, a sample response, the
  existing model).
- Do not infer the server's layering from the client.

## Do not

- Generate a parallel FastAPI service "for later"
- Recommend a rewrite into the templated stack
- Apply Dart naming to their code, or their naming to the Dart code
