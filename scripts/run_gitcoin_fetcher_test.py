import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())
from fetchers.gitcoin import _fetch_gitcoin_rounds
from config import get_settings

async def main():
    s = get_settings()
    print('Using GITCOIN URL:', s.gitcoin_graphql_url)
    rounds = await _fetch_gitcoin_rounds(s.gitcoin_graphql_url)
    print('Rounds fetched count:', len(rounds))
    for r in rounds:
        print(r)

if __name__ == '__main__':
    asyncio.run(main())
