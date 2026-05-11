# Bug Investigation

## 1. Symptoms
- What is the observed failure? (error message, wrong output, crash, performance degradation, etc.)
- Include exact error logs or screenshots.
- When does it occur? (always, under certain conditions, randomly)

## 2. Reproduction Steps
- Minimal steps to reproduce the issue.
- Required environment (OS, Python version, dependencies, environment variables).
- Any specific data or configuration needed.

## 3. Root Cause Analysis
- What is the underlying cause? (code logic, external API change, configuration drift, race condition, type mismatch, etc.)
- How was it identified? (logging, debugging, static analysis, bisecting changes)
- Include links to relevant code sections or external documentation.

## 4. Proposed Fix
- Detailed description of changes.
- Code snippets or patch if applicable.
- Any configuration changes (e.g., environment variables, API keys).

## 5. Verification
- How to confirm the fix works (unit tests, manual test steps, monitoring metrics).
- Expected results after fix (e.g., no error, correct output, performance improvement).

## 6. Regression Risks
- What other parts of the system could be affected?
- How to mitigate (additional tests, feature flags, gradual rollout).

## 7. Type Checking & Static Analysis Notes (if applicable)
- If the issue is related to a static type checker (Pyrefly, mypy, etc.):
  - What was the exact error?
  - Why does the type checker flag it (incorrect type stub, missing overload, etc.)?
  - How was it resolved? (e.g., added `# type: ignore`, updated type hints, refactored code)
- Record any suppression comments with a clear explanation.

## 8. LLM / External API Fallback Issues
- For problems with OpenAI, Groq, OpenRouter, Modal, etc.:
  - Which provider failed?
  - Error code and message (e.g., 404, 429, `json_validate_failed`).
  - Was the fallback chain triggered correctly?
  - How was the issue fixed? (retry logic, prompt adjustment, JSON extraction, key rotation)

## 9. Lessons Learned / Prevention
- What can be done to avoid similar issues in the future?
- Update documentation, add tests, improve error handling, enhance monitoring.

## Example: Pyrefly overload error in `llm_client.py`
- **Symptoms**: `No matching overload found` for `client.chat.completions.create`.
- **Reproduction**: Run `python -c "import backend.api.llm_client"` with Pyrefly enabled.
- **Root Cause**: The `response_format` parameter expects a specific type (`ResponseFormatJSONObject`) but a plain dict was passed; type stubs are incomplete for the OpenRouter client.
- **Fix**: Removed `response_format` and used regex extraction instead (or added `# type: ignore`).
- **Verification**: Import no longer produces type error; runtime still works with plain JSON extraction.
- **Regression Risks**: None, as the change simplifies the call and makes it more robust.