import os
import logging

from eth_account import Account

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

RPCS = {
    421614: "https://sepolia-rollup.arbitrum.io/rpc",
    84532: "https://sepolia.base.org",
    534351: "https://sepolia-rpc.scroll.io",
}

USDC = {
    421614: "0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d",
    84532: "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
}


OPERATOR_PK = os.getenv("OPERATOR_PK")
OPERATOR = Account.from_key(OPERATOR_PK)

FACTORY = os.getenv("FACTORY")
