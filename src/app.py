import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from eth_account import Account
from web3 import AsyncWeb3
from web3.contract import AsyncContract

from config import RPCS, OPERATOR_PK, FACTORY

logger = logging.getLogger("app")


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


@app.get("/call")
async def call(chain_id: int, for_: str, to: str, value: int, data: str) -> str:
    logger.info(f"{chain_id=}, {for_=}, {to=}, {value=}, {data=}")

    w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(RPCS[chain_id]))
    operator = Account.from_key(OPERATOR_PK)

    factory: AsyncContract = w3.eth.contract(FACTORY, abi=factory_abi)
    [deployed, from_] = await factory.functions.getWallet(for_, 0).call()

    tx_params = {
        "from": operator.address,
        "nonce": await w3.eth.get_transaction_count(operator.address),
    }

    if not deployed:
        raw_tx = await factory.functions.createWalletAndCall(
            for_,
            0,
            [0, chain_id, from_, to, value, data],
        ).build_transaction(tx_params)
        tx_hash = await w3.eth.send_raw_transaction(
            operator.sign_transaction(raw_tx).rawTransaction
        )
    else:
        contract: AsyncContract = w3.eth.contract(from_, abi=wallet_abi)
        raw_tx = await contract.functions.operatorCall(
            [
                await contract.functions.nonces(from_).call(),
                chain_id,
                from_,
                to,
                value,
                data,
            ]
        ).build_transaction(tx_params)
        tx_hash = await w3.eth.send_raw_transaction(
            operator.sign_transaction(raw_tx).rawTransaction
        )

    return tx_hash.hex()
