# Code Standards Rules

## Naming
- MUST use descriptive test names: `test_{behavior_being_tested}` not `test_1` or `test_function_name`.
- MUST NOT use abbreviations in variable names unless universally understood (`id`, `url`, `npi`, `ndc` OK).

## Error Handling
- MUST catch specific exceptions — never bare `except` or `except Exception: pass`.
- MUST log caught exceptions with structured context (`correlation_id`, `tenant_id`, `entity_id`).
- MUST NOT swallow exceptions silently.

## Imports
- MUST NOT have unused imports (ruff F401).
- MUST NOT have duplicate dependencies in `pyproject.toml`.

## Configuration
- MUST NOT hardcode timeouts, limits, thresholds, or magic numbers — use settings/constants.
- MUST externalize ML hyperparameters — never hardcode `learning_rate`, `n_estimators`, etc.

## Dead Code
- MUST NOT commit empty stub files, empty test directories, or unused modules.
- MUST delete dead code — git has history.

## Logging Keys (LESSON-005)
- MUST NOT use reserved `LogRecord` attribute names in `extra={}`: `name`, `msg`, `args`, `levelname`, `levelno`, `pathname`, `filename`, `module`, `exc_info`, `exc_text`, `stack_info`, `lineno`, `funcName`, `created`, `msecs`, `relativeCreated`, `thread`, `threadName`, `processName`, `process`, `message`, `asctime`.
- MUST prefix structured log keys with subsystem: `audit_action`, `auth_user_id`, `svc_name`.
