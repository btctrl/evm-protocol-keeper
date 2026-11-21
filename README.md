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
