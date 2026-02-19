OctoPrint plugin that records 3D print jobs directly on-chain via the [MINT Protocol](https://github.com/FoundryNet/foundry_net_MINT) on Solana. No intermediary API. Your printer signs its own transactions.

## Install

In OctoPrint Plugin Manager, install from URL:
```
https://github.com/FoundryNet/OctoPrint-MINT/archive/main.zip
```

Or via pip:
```
pip install solders solana base58
pip install https://github.com/FoundryNet/OctoPrint-MINT/archive/main.zip
```

## Setup

1. Generate or use an existing Solana keypair (this is your machine identity)
2. Go to **Settings > MINT Protocol**
3. Set your **fee payer keypair path** (needs small SOL balance for tx fees)
4. Print anything. Earn MINT.

A machine keypair is auto-generated on first run at `~/.foundry/octoprint_machine_keypair.json`.

## How It Works

1. Print completes in OctoPrint
2. Plugin calls `record_job` directly on the Solana program
3. Helius webhook fires, ML pipeline scores the job
4. `settle_job` executes automatically
5. MINT tokens land in your wallet

Base rate: **0.005 MINT/second** (18 MINT/hour). 96% to you, 4% protocol fees.

## Earnings (established printer, 30+ jobs)

| Duration | You Get (96%) | Total |
|----------|--------------|-------|
| 1 hour   | 17.28 MINT   | 18.00 |
| 4 hours  | 69.12 MINT   | 72.00 |
| 8 hours  | 138.24 MINT  | 144.00|

New printers start at 0.5x warmup, reaching full rate after 30 jobs.

## Links

- [MINT Protocol](https://github.com/FoundryNet/foundry_net_MINT)
- [Program on Solscan](https://solscan.io/account/4ZvTZ3skfeMF3ZGyABoazPa9tiudw2QSwuVKn45t2AKL)
- [MINT Token](https://solscan.io/token/5Pd4YBgFdih88vAFGAEEsk2JpixrZDJpRynTWvqPy5da)

## License

MIT
