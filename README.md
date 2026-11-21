# evm-protocol-keeper

Asynchronous EVM protocol keeper and automated maintenance engine built with Python and `web3.py`. Evaluates on-chain oracle freshness, price deviation thresholds, and EIP-1559 gas ceilings before triggering smart contract upkeep routines (`performUpkeep` / `harvest`).

## Architecture & B2B Use Cases
- **Condition-Based Execution (`checkUpkeep`):** Monitors Chainlink `AggregatorV3` round timestamps and price deviations concurrently against confirmed block state.
- **Gas Ceiling Protection:** Enforces a strict `MAX_GAS_GWEI` threshold so automated protocol maintenance never overpays during network congestion.
- **Safe Dry-Run & Live Modes:** Runs in zero-key simulation mode out of the box on Base Mainnet, ready to be wired into any `AutomationCompatible` vault, lending market, or treasury contract.

## Quickstart

```bash
git clone https://github.com/btctrl/evm-protocol-keeper
cd evm-protocol-keeper
cp .env.example .env
pip install -r requirements.txt
python keeper.py
```

## Example Output

```text
13:09:54 | INFO | Connected to Base Mainnet | Keeper Mode: DRY-RUN SIMULATION | Max Gas: 5.0 Gwei
13:09:54 | INFO | CheckUpkeep | Round #55340232221128671366 | ETH/USD: \$1,649.94 | Age: 619s | Dev: 0.0000% | Needed: True
13:09:54 | WARNING | UPKEEP TRIGGERED | Reason: Initial state sync / epoch baseline trigger | ETH/USD: \$1,649.94 | BaseFee: 0.005000 Gwei
13:09:54 | INFO | UPKEEP EXECUTED (Dry-Run) | Round #55340232221128671366 synced at \$1,649.94
13:09:59 | INFO | CheckUpkeep | Round #55340232221128671366 | ETH/USD: \$1,649.94 | Age: 624s | Dev: 0.0000% | Needed: False
```
