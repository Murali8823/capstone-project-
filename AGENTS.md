# Repository Guidelines

## Project Structure & Module Organization

The mobile client is an Expo/React Native app using Expo Router. Route screens live in `app/` (`index.tsx` is the main screen and `_layout.tsx` defines the root layout). The simulated LAN API is in `backend/server.py`; it persists demo state to `demo_state.json` at the repository root when run. `app.json`, `tsconfig.json`, and `package.json` hold Expo, TypeScript, and npm configuration. `report.md` documents setup and demo scenarios. There is currently no dedicated test or asset directory.

## Build, Test, and Development Commands

- `npm.cmd install` installs JavaScript dependencies on Windows.
- `npx expo start --lan` starts the Expo development server for devices on the local network.
- `py -3 backend/server.py` starts the simulated API; set `EXPO_PUBLIC_API_URL` to the computer's Wi-Fi address and port `8765` in the client environment.
- `npx tsc --noEmit` checks TypeScript types without emitting files.

There is no configured build, lint, or automated test script in `package.json`. Follow the Expo install and three-device instructions in `report.md` when validating the demo manually.

## Coding Style & Naming Conventions

Use TypeScript/TSX for client code and Python for the API. TypeScript strict mode is enabled; preserve useful types and avoid suppressing errors. Use two-space indentation in TS/TSX, and follow the existing four-space Python function-body indentation. Use PascalCase for React components and types, camelCase for variables and functions, and snake_case for Python functions and variables. Keep UI work in `app/` and API behavior in `backend/`.

## Testing Guidelines

No test framework or coverage threshold is configured. For client changes, run `npx tsc --noEmit` and exercise the affected screen in Expo Go. For API changes, start `py -3 backend/server.py` and check the relevant endpoint or payment flow using the demo walkthrough. Do not use real payment credentials or user data; all balances and outcomes are simulated.

## Commit & Pull Request Guidelines

This checkout has no accessible Git history, so no repository-specific commit convention can be confirmed. Use concise imperative commit subjects, for example `Add payment review state`. Pull requests should describe the user-visible change, list validation performed, link any related issue, and include screenshots for UI changes. Call out changes to API behavior or the demo setup steps in `report.md`.

## Security & Configuration

Keep the API bound to the local demo workflow and use only synthetic profiles and transactions. Configure the client API URL through `EXPO_PUBLIC_API_URL`; do not commit secrets, real personal data, or generated `demo_state.json` runtime data.
