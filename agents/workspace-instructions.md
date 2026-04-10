# Workspace Instructions for NextMark Delivery App

## Project Organization and SRP (Single Responsibility Principle)
- **Modular Structure**: Keep code organized into small, focused modules/classes/functions. Each component should have a single responsibility (e.g., backend routers handle only API endpoints, frontend components manage only UI logic).
- **Separation of Concerns**: Isolate business logic (e.g., route optimization in `Back_end/Delivery_app_BK/route_optimization/`), data access (models/schemas), and presentation (frontend apps). Avoid mixing Flask API logic with React rendering.
- **Shared Resources**: Use `Front_end/packages/` for reusable code across admin-app and driver-app. Do not duplicate logic; import from shared packages.
- **File Naming and Structure**: Use descriptive names (e.g., `google_client.py` for Google API interactions). Group related files in folders (e.g., `providers/`, `services/`). Limit files to 300-500 lines; split if larger.
- **Imports and Dependencies**: Keep imports minimal and organized (standard libs first, then third-party, then local). Pin versions in `requirements.txt` and `package.json` for reproducibility.

## Development Workflow: Plan → Implement → Test
- **Planning Phase**: Before coding, outline the feature/refactor in comments or a plan document. Identify affected files, dependencies, and edge cases. Reference existing patterns (e.g., error handling in `Back_end/Delivery_app_BK/errors/`).
- **Implementation Phase**: Write clean, readable code with type hints (Python) or TypeScript interfaces. Follow DRY (Don't Repeat Yourself). Use async/await for I/O in backend; hooks/effects in React.
- **Testing Phase**: Add unit tests (pytest for backend, Jest for frontend) for new logic. Include integration tests for API endpoints and UI components. Run tests before commits; aim for 80%+ coverage.
- **Validation**: After changes, run builds/lints (e.g., `npm run build` in frontend, `pytest` in backend). Fix errors immediately. Use tools like ESLint/Prettier for frontend consistency.
- **Documentation**: Add JSDoc/docstrings for public functions. Update READMEs if APIs change.

## General Best Practices
- **Error Handling**: Use custom exceptions (e.g., from `errors/`) and graceful fallbacks. Log errors without exposing sensitive data.
- **Security**: Validate inputs; use HTTPS; avoid hardcoding secrets (use env vars or AWS credentials).
- **Performance**: Optimize queries (e.g., via SQLAlchemy), lazy-load in React, and cache where possible.
- **Code Reviews**: Assume changes will be reviewed; write self-documenting code.
- **Commits**: Use clear messages (e.g., "feat: add route optimization endpoint"). Commit frequently with tests passing.

These rules apply to all files in the workspace. For specific features, provide detailed prompts with file paths.
