import os
import logging

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

RPCS = {
    421614: "https://sepolia-rollup.arbitrum.io/rpc",
    84532: "https://sepolia.base.org",
}

OPERATOR_PK = os.getenv("OPERATOR_PK")
FACTORY = os.getenv("FACTORY")
