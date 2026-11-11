# ShieldPay LAN Demo

ShieldPay demonstrates receiver-score payment decisions and local smart-contract escrow using synthetic balances. It includes one Expo mobile app for five roles, a shared Python/SQLite LAN backend, a local Hardhat chain, and a desktop security dashboard.

## Quick start on Windows

Install Node.js and Python 3.13 first. If `node_modules` is missing, install the pinned JavaScript tree once (the legacy peer resolver is needed because the existing Expo packages declare a React/react-dom peer mismatch):

```powershell
npm.cmd install --legacy-peer-deps
```

Open four PowerShell terminals at the repository root.

1. **Local blockchain**

   ```powershell
   npm.cmd run chain:node
   ```

2. **Compile and deploy** (second terminal)

   ```powershell
   npm.cmd run chain:compile
   npm.cmd run chain:deploy
   ```

3. **Shared backend** (third terminal)

   ```powershell
   py -3 backend/server.py
   ```

4. **Expo app** (fourth terminal; replace this IP after checking `ipconfig`)

   ```powershell
   $env:EXPO_PUBLIC_API_URL = 'http://192.168.1.19:8765'
   npx.cmd expo start --lan
   ```

Open `http://<computer-wifi-ip>:8765/dashboard` on the desktop and sign in with demo password `shieldpay-admin`. On five phones on the same Wi-Fi, open Expo Go and scan the Expo QR; assign Maya, Arjun, Riya, Suspicious Profile and Northstar Gadgets once each.

For a 10-second escrow countdown, set `$env:SHIELDPAY_ESCROW_TIMEOUT_SECONDS='10'` in the backend terminal before starting it. See [docs/NETWORK_SETUP.md](docs/NETWORK_SETUP.md) for IP, firewall, environment and troubleshooting steps.

## Decision rules

- Score below 50%: approve and transfer simulated value immediately.
- Score 50%–80% inclusive: lock value in the local contract when deployed.
- Score above 80%: reject without debiting sender.

Business starts at 65%; suspicious persona starts at 95%. All balances and local-chain test ETH are simulated. There is no AI model, bank, UPI, card or payment-gateway connection.

## Technical documentation

Start with [Project Overview](docs/PROJECT_OVERVIEW.md), [System Architecture](docs/SYSTEM_ARCHITECTURE.md), [API Documentation](docs/API_DOCUMENTATION.md), [Blockchain and Escrow](docs/BLOCKCHAIN_AND_ESCROW.md), [Demo Scenarios](docs/DEMO_SCENARIOS.md), [Academic Review Explanation](docs/ACADEMIC_REVIEW_EXPLANATION.md) and [Development Progress](docs/DEVELOPMENT_PROGRESS.md). The full required document index is under `docs/`.

## Current verification boundary

Python compile/API, Expo TypeScript/Android bundle, Hardhat tests, live backend-to-local-chain lifecycle, dashboard JavaScript and same-host LAN-address checks passed. Physical five-phone/Expo Go operation and real browser visual interaction still require manual review. Do not expose ports 8765 or 8545 to the public internet.
