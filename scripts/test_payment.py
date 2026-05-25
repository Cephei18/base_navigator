from __future__ import annotations

import argparse
import asyncio
import os


async def main() -> None:
    parser = argparse.ArgumentParser(description="Call a paid Base Navigator endpoint with x402.")
    parser.add_argument("--url", default="http://localhost:8000/api/governance")
    args = parser.parse_args()

    private_key = os.getenv("EVM_PRIVATE_KEY")
    if not private_key:
        raise SystemExit("Set EVM_PRIVATE_KEY with a funded Base Sepolia wallet private key.")

    from eth_account import Account
    from x402 import x402Client
    from x402.http.clients import x402HttpxClient
    from x402.mechanisms.evm import EthAccountSigner
    from x402.mechanisms.evm.exact.register import register_exact_evm_client

    client = x402Client()
    account = Account.from_key(private_key)
    register_exact_evm_client(client, EthAccountSigner(account))

    async with x402HttpxClient(client) as http:
        response = await http.post(args.url)
        print(response.status_code)
        print(response.text)


if __name__ == "__main__":
    asyncio.run(main())
