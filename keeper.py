import asyncio
import logging
import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple
from dotenv import load_dotenv
from web3 import AsyncWeb3, AsyncHTTPProvider

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("protocol-keeper")

RPC_URL = os.getenv("RPC_URL", "https://base-rpc.publicnode.com")

# Chainlink ETH/USD Aggregator Proxy on Base Mainnet (20min Heartbeat, 8 Decimals)
ORACLE_ADDRESS = AsyncWeb3.to_checksum_address(
    os.getenv("ORACLE_ADDRESS", "0x71041dddad3595F9CEd3DcCFBe3D1F4b0a16Bb70")
)
HEARTBEAT_THRESHOLD_SEC = int(os.getenv("HEARTBEAT_THRESHOLD_SEC", "1200"))
DEVIATION_THRESHOLD_PCT = Decimal(os.getenv("DEVIATION_THRESHOLD_PCT", "0.25"))
MAX_GAS_GWEI = Decimal(os.getenv("MAX_GAS_GWEI", "5.0"))
KEEPER_PRIVATE_KEY = os.getenv("KEEPER_PRIVATE_KEY", "")

AGGREGATOR_V3_ABI = [
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "latestRoundData",
        "outputs": [
            {"internalType": "uint80", "name": "roundId", "type": "uint80"},
            {"internalType": "int256", "name": "answer", "type": "int256"},
            {"internalType": "uint256", "name": "startedAt", "type": "uint256"},
            {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
            {"internalType": "uint80", "name": "answeredInRound", "type": "uint80"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


@dataclass
class UpkeepCondition:
    upkeep_needed: bool
    reason: str
    current_price: Decimal
    oracle_age_sec: int
    deviation_pct: Decimal
    round_id: int


class EvmProtocolKeeper:
    def __init__(self, rpc_url: str) -> None:
        self.w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        self.oracle = self.w3.eth.contract(address=ORACLE_ADDRESS, abi=AGGREGATOR_V3_ABI)
        self.last_reported_price: Optional[Decimal] = None
        self.decimals: int = 8

    async def initialize(self) -> None:
        if not await self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {RPC_URL}")
        self.decimals = await self.oracle.functions.decimals().call()
        mode = "LIVE SIGNING" if KEEPER_PRIVATE_KEY else "DRY-RUN SIMULATION"
        logger.info(f"Connected to Base Mainnet | Keeper Mode: {mode} | Max Gas: {MAX_GAS_GWEI} Gwei")

    async def check_upkeep(self) -> UpkeepCondition:
        latest_block, round_data = await asyncio.gather(
            self.w3.eth.get_block("latest"),
            self.oracle.functions.latestRoundData().call(),
        )

        block_ts = int(latest_block["timestamp"])
        round_id, answer, _, updated_at, _ = round_data
        current_price = Decimal(answer) / Decimal(10**self.decimals)
        oracle_age_sec = max(0, block_ts - int(updated_at))

        if self.last_reported_price is None:
            self.last_reported_price = current_price
            return UpkeepCondition(
                upkeep_needed=True,
                reason="Initial state sync / epoch baseline trigger",
                current_price=current_price,
                oracle_age_sec=oracle_age_sec,
                deviation_pct=Decimal("0"),
                round_id=round_id,
            )

        deviation_pct = (
            abs(current_price - self.last_reported_price) / self.last_reported_price
        ) * Decimal(100)

        if oracle_age_sec >= HEARTBEAT_THRESHOLD_SEC:
            return UpkeepCondition(
                upkeep_needed=True,
                reason=f"Oracle heartbeat stale ({oracle_age_sec}s >= {HEARTBEAT_THRESHOLD_SEC}s)",
                current_price=current_price,
                oracle_age_sec=oracle_age_sec,
                deviation_pct=deviation_pct,
                round_id=round_id,
            )

        if deviation_pct >= DEVIATION_THRESHOLD_PCT:
            return UpkeepCondition(
                upkeep_needed=True,
                reason=f"Price deviation threshold reached ({deviation_pct:.4f}% >= {DEVIATION_THRESHOLD_PCT}%)",
                current_price=current_price,
                oracle_age_sec=oracle_age_sec,
                deviation_pct=deviation_pct,
                round_id=round_id,
            )

        return UpkeepCondition(
            upkeep_needed=False,
            reason="Nominal state",
            current_price=current_price,
            oracle_age_sec=oracle_age_sec,
            deviation_pct=deviation_pct,
            round_id=round_id,
        )

    async def get_current_gas_gwei(self) -> Tuple[Decimal, int]:
        block = await self.w3.eth.get_block("latest")
        base_fee_wei = block.get("baseFeePerGas", 0)
        gas_gwei = Decimal(base_fee_wei) / Decimal(10**9)
        return gas_gwei, base_fee_wei

    async def perform_upkeep(self, condition: UpkeepCondition) -> None:
        gas_gwei, _ = await self.get_current_gas_gwei()
        if gas_gwei > MAX_GAS_GWEI:
            logger.warning(
                f"UPKEEP DEFERRED | Gas price {gas_gwei:.4f} Gwei exceeds ceiling ({MAX_GAS_GWEI} Gwei)"
            )
            return

        logger.warning(
            f"UPKEEP TRIGGERED | Reason: {condition.reason} | "
            f"ETH/USD: ${condition.current_price:,.2f} | BaseFee: {gas_gwei:.6f} Gwei"
        )

        # In production, sign & broadcast target contract performUpkeep(performData) here
        await asyncio.sleep(0.1)
        self.last_reported_price = condition.current_price
        logger.info(
            f"UPKEEP EXECUTED (Dry-Run) | Round #{condition.round_id} synced at ${condition.current_price:,.2f}"
        )

    async def run(self, poll_interval: float = 5.0) -> None:
        await self.initialize()
        while True:
            try:
                condition = await self.check_upkeep()
                logger.info(
                    f"CheckUpkeep | Round #{condition.round_id} | ETH/USD: ${condition.current_price:,.2f} | "
                    f"Age: {condition.oracle_age_sec}s | Dev: {condition.deviation_pct:.4f}% | "
                    f"Needed: {condition.upkeep_needed}"
                )
                if condition.upkeep_needed:
                    await self.perform_upkeep(condition)
            except Exception as exc:
                logger.error(f"Keeper loop error: {exc}")

            await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    keeper = EvmProtocolKeeper(rpc_url=RPC_URL)
    try:
        asyncio.run(keeper.run(poll_interval=5.0))
    except KeyboardInterrupt:
        logger.info("Protocol keeper stopped gracefully.")
