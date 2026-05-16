---
trigger: always_on
---

# Project Rules

## General
- Never modify unrelated files
- Never refactor without approval
- Keep implementations minimal
- Preserve existing architecture

## Architecture
- Use service abstraction
- Avoid direct provider coupling
- Keep modules isolated

## Scraping
- Providers must implement common interface
- Handle retry and rate limit
- Never hardcode cookies or tokens
- Run scraper locally (not on GitHub Actions) to avoid IP blocking; use Windows Task Scheduler or equivalent for periodic execution

## Database
- Use repositories
- Avoid raw SQL outside data layer

## AI Engine
- All providers require fallback support
- Never block async pipeline

## Testing
- New features require tests
- Never delete tests without approval