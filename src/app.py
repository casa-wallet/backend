import logging
import asyncio

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from eth_abi import encode
from web3 import AsyncWeb3
from web3.contract import AsyncContract

from config import RPCS, OPERATOR, FACTORY, USDC

logger = logging.getLogger("app")
lock = asyncio.Lock()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


factory_abi = [
    {"inputs": [], "stateMutability": "nonpayable", "type": "constructor"},
    {"inputs": [], "name": "ERC1167FailedCreateClone", "type": "error"},
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "uint256", "name": "index", "type": "uint256"},
        ],
        "name": "createWallet",
        "outputs": [{"internalType": "address", "name": "wallet", "type": "address"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "uint256", "name": "index", "type": "uint256"},
            {
                "components": [
                    {"internalType": "uint128", "name": "nonce", "type": "uint128"},
                    {"internalType": "uint128", "name": "chainId", "type": "uint128"},
                    {"internalType": "address", "name": "from", "type": "address"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "value", "type": "uint256"},
                    {"internalType": "bytes", "name": "data", "type": "bytes"},
                ],
                "internalType": "struct Wallet.CasaCall",
                "name": "call",
                "type": "tuple",
            },
        ],
        "name": "createWalletAndCall",
        "outputs": [{"internalType": "address", "name": "wallet", "type": "address"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "uint256", "name": "index", "type": "uint256"},
        ],
        "name": "getWallet",
        "outputs": [
            {"internalType": "bool", "name": "exists", "type": "bool"},
            {"internalType": "address", "name": "wallet", "type": "address"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "implementation",
        "outputs": [{"internalType": "contract Wallet", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]
wallet_abi = [
    {
        "inputs": [{"internalType": "address", "name": "owner", "type": "address"}],
        "name": "nonces",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "uint128", "name": "nonce", "type": "uint128"},
                    {"internalType": "uint128", "name": "chainId", "type": "uint128"},
                    {"internalType": "address", "name": "from", "type": "address"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "value", "type": "uint256"},
                    {"internalType": "bytes", "name": "data", "type": "bytes"},
                ],
                "internalType": "struct Wallet.CasaCall",
                "name": "call",
                "type": "tuple",
            }
        ],
        "name": "operatorCall",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]
token_abi = []


def get_w3(chain_id: int) -> AsyncWeb3:
    return AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(RPCS[chain_id]))


async def get_wallet_address(chain_id: int, for_: str):
    w3 = get_w3(chain_id)
    factory: AsyncContract = w3.eth.contract(FACTORY, abi=factory_abi)
    [deployed, from_] = await factory.functions.getWallet(for_, 0).call()
    return (deployed, from_)


async def call_with_deploy(chain_id: int, for_: str, to: str, data: str, value: int):
    w3 = get_w3(chain_id)

    (deployed, from_) = await get_wallet_address(chain_id, for_)

    if deployed:
        contract: AsyncContract = w3.eth.contract(from_, abi=wallet_abi)
        fn = contract.functions.operatorCall(
            [
                await contract.functions.nonces(from_).call(),
                chain_id,
                from_,
                to,
                value,
                data,
            ]
        )
    else:
        factory: AsyncContract = w3.eth.contract(FACTORY, abi=factory_abi)
        fn = factory.functions.createWalletAndCall(
            for_,
            0,
            [0, chain_id, from_, to, value, data],
        )

    async with lock:
        raw_tx = await fn.build_transaction(
            {
                "from": OPERATOR.address,
                "nonce": await w3.eth.get_transaction_count(OPERATOR.address),
            }
        )
        tx_hash = await w3.eth.send_raw_transaction(
            OPERATOR.sign_transaction(raw_tx).rawTransaction
        )

    return tx_hash.hex()


async def claim_fee(
    tx_hash: str, tx_chain_id: int, fee_chain_id: int, fee_amount: float, for_: str
):
    tx_w3 = get_w3(tx_chain_id)
    await tx_w3.eth.wait_for_transaction_receipt(tx_hash)

    data = (
        "0xa9059cbb"
        + encode(
            ["address", "uint256"], [OPERATOR.address, int(fee_amount * 1e6)]
        ).hex()
    )  # transfer(operator.address, fee_amount)

    try:
        tx_hash = await call_with_deploy(
            fee_chain_id, for_, USDC[fee_chain_id], data, 0
        )
        logger.info(f"Fee tx: {fee_chain_id}:{tx_hash}")
    except Exception as e:
        logger.warning(f"Cant pay fee, {e}")


@app.get("/call")
async def call(
    chain_id: int,
    for_: str,
    to: str,
    data: str,
    bg: BackgroundTasks,
    value: int = 0,
) -> str:
    w3 = get_w3(chain_id)
    for_ = w3.to_checksum_address(for_)
    to = w3.to_checksum_address(to)

    logger.info(f"{chain_id=}, {for_=}, {to=}, {value=}, {data=}")
    tx_hash = await call_with_deploy(chain_id, for_, to, data, value)
    logger.info(f"Call tx: {chain_id}:{tx_hash}")

    bg.add_task(claim_fee, tx_hash, chain_id, 421614, 0.1, for_)
    bg.add_task(claim_fee, tx_hash, chain_id, 84532, 0.1, for_)

    return tx_hash
