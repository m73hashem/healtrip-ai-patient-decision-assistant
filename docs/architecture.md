# Architecture decision record

## Why FastAPI instead of NestJS?

The assignment allows any backend framework. FastAPI keeps the prototype compact and makes typed tool schemas and validation easy to inspect. It also matches the backend/AI service boundary of the project.

## Why explicit tool calling?

The important engineering question is how provider recommendations are grounded in trusted data. The model requests a tool, but application code performs the query and builds structured recommendations from returned database records. Generated prose is instructed to discuss provider categories generically; it is not independently validated as a source of provider identities.

## Why no RAG/vector database?

The prototype has a small structured provider dataset. SQL filtering is simpler and more deterministic. RAG would add complexity without solving the main problem demonstrated here.

## Why not let the model decide emergency care alone?

Medical triage has higher safety requirements than ordinary recommendation. The agent instructions direct potentially emergent cases toward emergency medical evaluation, and a small deterministic emergency phrase guard runs in the backend before normal model and provider-search handling. The guard covers a limited set of obvious prototype examples and is intentionally lightweight; it is not a medical diagnosis system or clinical triage engine. It demonstrates a basic safety boundary and does not cover every emergency or replace clinical assessment.
