# ShieldPay Expo Demo

A simulated-wallet Expo app for demonstrating risk-aware transfers between three Android phones on the same Wi-Fi.

See [report.md](report.md) for setup, the three-device walkthrough, simulated risk scenarios, limitations, and troubleshooting.

## Quick start

1. Start the LAN API: `py -3 backend/server.py`
2. In another terminal set `EXPO_PUBLIC_API_URL` to `http://<computer-wifi-ip>:8765`.
3. Run `npm.cmd install`, the Expo install commands in `report.md`, then `npx expo start --lan`.
4. Open the Expo QR with Expo Go on three Android phones and choose a different demo identity on each.

All balances and transfers are simulated. Never connect this demo to payment rails or real user data.
"# capstone-project-" 
