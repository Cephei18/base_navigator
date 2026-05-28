import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())
from fetchers.neynar import fetch_social_casts
from config import get_settings

async def main():
    s = get_settings()
    print('NEYNAR_API_KEY present?', bool(s.neynar_api_key))
    casts = await fetch_social_casts(limit=5)
    print('Casts fetched count:', len(casts))
    for c in casts:
        print(c.get('text')[:120])

if __name__ == '__main__':
    asyncio.run(main())
