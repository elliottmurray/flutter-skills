# Cross-language test techniques

Background for choosing how a Dart/Python pair shares its tests. The shipped
flavours are the first two rows. The others are established open-source
approaches to use when a pair outgrows them.

| Technique | Precedent | Fits | Cost |
|---|---|---|---|
| **Twinned tests (intent)** | Mirrored suites in polyglot SDKs | Any model or logic. Each side keeps its own idiom | Twins drift unless something compares them. The hook does that by name |
| **Data-driven test vectors (shared)** | [JSON-Schema-Test-Suite](https://github.com/json-schema-org/JSON-Schema-Test-Suite) (`description`/`data`/`valid`, run by dozens of validators across languages), crypto and protocol conformance vectors | Models, parsers, validators, pure functions: input → output or error | Only data can be shared. Behaviour needing mocks or time does not fit |
| **Gherkin feature files** | Cucumber. [`pytest-bdd`](https://pypi.org/project/pytest-bdd/) on Python, [`bdd_widget_test`](https://pub.dev/packages/bdd_widget_test) on Flutter | Business logic described as scenarios that both sides implement | Two step-definition layers to maintain, and Dart tooling is thinner |
| **Schema-first codegen** | JSON Schema or OpenAPI → [`datamodel-code-generator`](https://pypi.org/project/datamodel-code-generator/) (Pydantic) and [`quicktype`](https://github.com/glideapps/quicktype) or `openapi-generator` (Dart) | Large or fast-changing contracts where hand-written twins become busywork | Generated code is harder to customise, and validation rules beyond types often do not survive generation |
| **Consumer-driven contracts** | [Pact](https://docs.pact.io/) | HTTP request/response shapes between deployed services | Needs a broker, and covers the endpoint rather than the model's rules |

## Extending vectors past models

The vector format works for a pure function if `data` holds the arguments and
`expected` the return value. Keep `valid`/`error_field` for the rejection
path. Write a new loader per function shape rather than generalising the
model one. Once a case needs a fake clock, a mock repository or ordering
between calls, the function has collaborators and belongs in twinned tests.
