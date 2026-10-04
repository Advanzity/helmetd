# Shared road hazards on Solana

A rider reports debris, a pothole, a blocked lane, or standing water. Other riders
read signed reports near their location from the same Solana devnet. The chain
is the shared event log; no Helmetd server/database is required. A reader trusts
an explicit group of rider public keys. Signatures establish the reporting wallet,
not whether a road observation is true. No tokens, rewards or payments are minted.

Reports use the deployed SPL Memo program, so this prototype needs no custom
program deployment. The memo contains a random report ID, category, approximate
coordinates (three decimal places), timestamp, expiry, and a demo marker. These
fields and the wallet address are public and persist on-chain after expiry. Camera
frames, person/vehicle detections, names and continuous location tracks are never
included. Expiry only hides a report from active results; it does not erase it.

## Two-rider demo

From the repository root:

```sh
uv sync --locked --extra audio
uv run helmetd-hazards init
uv run helmetd-hazards airdrop
```

The wallet is stored at `.local/hazards/devnet-wallet.json` with mode 0600 and is
ignored by Git. Only its public address is printed. The program verifies devnet's
genesis hash before any operation and refuses other clusters. Test SOL has no
monetary value. If the faucet is rate-limited, use <https://faucet.solana.com> to
fund the printed address; 0.01 devnet SOL is ample for this demo.

Publish a **simulated** report at explicitly chosen example coordinates:

```sh
uv run helmetd-hazards report debris --lat 42.123 --lon -83.123 --demo
```

It prints an explorer link before submission and a confirmation only after the
chain confirms. A signed packet is saved in `.local/hazards/outbox/` before sending.
If the response is uncertain, check the printed signature with
`uv run helmetd-hazards confirm SIGNATURE`; do not blindly create another report.

On a second computer, a reader needs only the reporter's **public** address:

```sh
uv run helmetd-hazards nearby --rider REPORTER_PUBLIC_KEY \
  --lat 42.123 --lon -83.122 --include-demo
```

Add another `--rider KEY` for each trusted rider (up to eight). `--radius` defaults
to 1000 metres; `--json` provides structured results. Normal queries omit demo
reports. The scan covers the newest 100 transactions per wallet within the last
hour. This bounded pilot feed is not an exhaustive global hazard search.

Reports expire after 15 minutes by default (`--ttl 60..3600`). A reporter can
retract their report, or two distinct trusted rider wallets can independently
report it cleared:

```sh
uv run helmetd-hazards clear REPORT_ID
```

One other rider's clear observation is shown but does not remove the report.
Repeated observations by the same wallet count once. Trust in multiple wallets
is not proof of independent people; a public network would need abuse controls.

## Browser reporting and spoken warnings

The Mac console at `http://127.0.0.1:8016/` integrates this feed with real browser
location and routes. Voice reporting saves locally first; a separate confirmed
Share action publishes to devnet. Reports retain their original observation time
and expiry even when shared later. Protocol v2 signs lane and publication time;
readers still accept v1 reports with an unspecified lane. Use the updated reader
on each rider's device to see v2 reports.

Set `HELMETD_TRUSTED_RIDERS` in each rider's voice environment to the public wallet
keys they want to follow. The feed syncs every 30 seconds. The route matcher uses
approximate coordinates, so announcements say reported near the upcoming route,
not a confirmed obstruction in your lane. See [browser controls](../voice/README.md).

## Standalone CLI / GPS-file tools

Connect the private ElevenLabs agent's local tools once:

```sh
sh tools/voice.sh connect-hazards
export HELMETD_TRUSTED_RIDERS=REPORTER_PUBLIC_KEY,ANOTHER_PUBLIC_KEY
uv run helmetd-hazards demo-position --lat 42.123 --lon -83.122
sh tools/voice.sh
```

The integrated agent now uses browser reporting; use the browser console for
voice hazard commands. The CLI report/nearby commands and GPS-file helper remain
available for explicit bench testing. No public HTTP tunnel is needed.

The agent does not choose coordinates. Demo positions expire after five minutes.
For a future GPS adapter, atomically replace `.local/hazards/position.json` with:

```json
{"lat": 42.123, "lon": -83.123, "recorded_at": 1791060000, "demo": false}
```

`recorded_at` is the actual fix time in Unix seconds, updated by the GPS source;
non-demo positions older than ten seconds are rejected. **GPS is not connected
on the current bench.** The browser console now has automatic upcoming-route matching, map overlays and
Mac system-voice alerts; it uses its own fresh browser location rather than this
CLI position file. Native helmet hazard overlays are not implemented.
Local OpenCV cues remain independent of Solana and do not wait for the network.

## Verification

```sh
uv run pytest apps/hazards/tests
uv run ruff check apps/hazards
```

Tests use real Solana signing and verify wrong authors, corrupted signatures,
failed/unconfirmed transactions, expiry, distance filtering, demo isolation,
clear observations, stale locations and rejection of non-devnet networks.
Live publishing still requires devnet funding and a reachable RPC.

Protocol references: [SPL Memo](https://www.solana-program.com/docs/memo),
[address transaction index](https://solana.com/docs/rpc/http/getsignaturesforaddress),
[confirmed transactions](https://solana.com/docs/rpc/http/gettransaction).
