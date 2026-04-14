# Architecture Rules

## Module Structure
- MUST follow: `modules/{name}/src/{api,models,services,events,jobs,utils}/` structure.
- MUST have `main.py` with FastAPI app for every module that serves HTTP traffic.
- MUST have `README.md` for every implemented module.

## Shared Code
- MUST put cross-module utilities in `shared/` — never duplicate across modules.
- MUST import from `shared` for: money utils, encryption, tenant context, event bus, validation types.
- MUST NOT create module-local copies of shared utilities (`penny_allocate`, `EventBus` protocol, etc.).

## Dependencies
- MUST use `shared.db.session` for database sessions — no module-local session factories.
- MUST use `shared.events.bus.EventBus` ABC — no module-local `EventBus` protocols.

## API
- MUST use `async def` for all API route handlers — never sync `def` (blocks event loop).
- MUST use Pydantic models for all request/response schemas.
- MUST return structured error responses: `{"error": {"code": "...", "message": "...", "correlation_id": "..."}}`.

## Integration Contract (LESSON-006)
- Every middleware/router/pre-commit primitive MUST have at least one integration test that exercises it through the top-level application factory (`create_app()` or equivalent). Unit tests on the primitive alone are insufficient; they verify correctness of a component that may never run.
