# Network Setup and Startup

## One-command startup (Windows)

From the repository root, run:

```powershell
py -3 start_demo.py
```

The launcher starts Hardhat if port 8545 is free, verifies/reuses a live local contract deployment (deploying when needed), starts the backend if port 8765 is free, detects the current Wi-Fi IPv4 address, and starts Expo if port 8081 is free. It opens separate terminal windows for long-running services and prints the dashboard URL. Existing services are reused to avoid `EADDRINUSE`; if Expo is already running, restart it manually if its API URL was configured for an old Wi-Fi address. Press Ctrl+C in the launcher window to stop only the services it started. The local Hardhat RPC remains bound to loopback.

If Python fails with Windows “Access is denied”, the launcher cannot run until the Python runtime issue is fixed. The individual commands below remain available for troubleshooting.

## Find the host IPv4 address

Run `ipconfig` in PowerShell and read **IPv4 Address** under the connected **Wireless LAN adapter Wi-Fi**. During the latest check this host used `192.168.1.19/24` (gateway `192.168.1.254`). Earlier DHCP had assigned `192.168.0.101`, so this address can change. Always check again before the demo.

All phones and the desktop must share the same non-guest Wi-Fi without client isolation. The mobile app uses `EXPO_PUBLIC_API_URL`; set it to `http://<current-wifi-ip>:8765`. It must not use `localhost` from a phone. The code fallback is this host's current address, not a portable value. The dashboard is served from the backend at `http://<current-wifi-ip>:8765/dashboard` and derives the API host from that URL.

## Start the local blockchain

Install Node.js/Python beforehand. If the checkout has no `node_modules`, run the dependency install once from the project root:

```powershell
npm.cmd install --legacy-peer-deps
```

The legacy npm peer resolver is needed for the current Expo/React dependency tree. From the project root, open a terminal and run:

```powershell
npm.cmd run chain:node
```

Hardhat listens on `127.0.0.1:8545` only. It prints well-known development accounts/private keys; these are local fake accounts and must never be used on a public network. Do not expose port 8545 to the LAN.

## Compile and deploy the contract

In a second terminal:

```powershell
npm.cmd run chain:compile
npm.cmd run chain:deploy
```

Deployment writes `backend/chain_config.json` with the local chain ID, contract address, oracle address and ABI. That generated address file is ignored by Git. If the Hardhat node is restarted, its state is erased; redeploy the contract and restart the backend.

## Start the shared backend

In a third terminal:

```powershell
py -3 backend/server.py
```

It listens on `0.0.0.0:8765`, uses SQLite at `shieldpay.sqlite3`, and invokes the local ethers bridge for real contract operations when a deployment config exists. On this machine `py -3 --version` is Python 3.13.14 and `py -3 -m pip --version` is pip 26.1.2. No Python package installation is needed. The restricted automation sandbox itself cannot create this WindowsApps Python process; normal operator terminal invocation works when permitted.

For a shorter timeout in the same PowerShell process:

```powershell
$env:SHIELDPAY_ESCROW_TIMEOUT_SECONDS = '10'
py -3 backend/server.py
```

The minimum is 10 seconds; default is 300. At expiry the contract/backend mark manual review. Funds stay locked until an authenticated admin refund.

The local demo admin password defaults to `shieldpay-admin`. Before starting the backend, optionally set `SHIELDPAY_ADMIN_PASSWORD` and `SHIELDPAY_ADMIN_TOKEN_SECRET` for the presentation. Keep the service on a trusted private LAN and do not use real passwords or user/payment data.

Check the host API:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
Invoke-RestMethod http://127.0.0.1:8765/api/state
```

`/health` reports the SQLite app, SSE endpoint and whether the local contract RPC is connected. The backend's SSE stream is `http://<current-wifi-ip>:8765/api/stream`.

## Open the desktop dashboard

On the host computer or another device on the same Wi-Fi, open:

```text
http://<current-wifi-ip>:8765/dashboard
```

Sign in with the configured demo admin password. The dashboard uses authenticated REST requests for score changes/reset/review and SSE for live events.

## Start the five mobile interfaces

Open a fourth terminal. Replace the sample IP with the current Wi-Fi address:

```powershell
$env:EXPO_PUBLIC_API_URL = 'http://192.168.1.19:8765'
npx.cmd expo start --lan
```

Install Expo Go on five Android phones and scan the Expo development QR on each phone. On each device select a distinct profile: Maya, Arjun, Riya, Suspicious Profile, or Northstar Gadgets. All clients reach the same API/database. Profile selection is for demonstration only; it is not user authentication. The mobile screen refreshes the server snapshot every 1.8 seconds; the dashboard receives push events over SSE.

## Windows Firewall and LAN safety

Allow Python on **Private networks** if Windows Firewall prompts. If a firewall rule is needed, limit it to Private profile and TCP port 8765. Check that the phone and PC are not on guest Wi-Fi or behind client isolation. Do not forward ports on the router, expose the backend publicly, or expose Hardhat RPC port 8545 to the LAN.

## Verified connectivity

Host-local `GET /health`, `GET /api/state`, `/dashboard` and `/dashboard.js` were checked through loopback. The dashboard and health endpoint also returned HTTP 200 using the latest Wi-Fi address `192.168.1.19`; chain health reported connected to Hardhat and the deployed local contract. Earlier Phase 2 API checks used the then-current `192.168.0.101`. These checks were made from the host itself; a separate handset was not available for an end-to-end Wi-Fi test.

## Troubleshooting

- **Mobile says backend offline:** rerun `ipconfig`, update `EXPO_PUBLIC_API_URL`, restart Expo, and allow Python on Private networks.
- **Dashboard says local RPC offline:** start Hardhat node first; redeploy after every node restart; restart backend after deployment.
- **Contract calls fail:** check `/health`, confirm chain ID 31337, and redeploy `ShieldPayEscrow` with `npm.cmd run chain:deploy`.
- **Expo QR does not open:** confirm phone/PC are on the same Wi-Fi and use LAN mode.
- **Reset:** use the dashboard's admin-only Reset Demo button. It safely resolves open local escrows and resets app balances/score history; blockchain event history remains on the local chain.

### Latest host-side LAN verification (2026-11-11)

The current Wi-Fi IPv4 at verification was `192.168.1.19`. From the host, `GET http://192.168.1.19:8765/health` returned HTTP 200 with `ok:true`, `simulation_only:true`, SSE realtime mode, and a connected local chain at contract `0x59b670e9fA9D0A427751Af201D676719a970857b`. `/api/state` showed five seeded profiles, no transactions after reset, and business score 65. `/dashboard` returned HTTP 200. Expo Metro `/status` at `http://192.168.1.19:8081/status` returned HTTP 200. Because the address is DHCP-assigned, confirm it with `ipconfig` before starting Expo and replace it in `EXPO_PUBLIC_API_URL`. A physical phone-originated request remains to be checked during setup.
