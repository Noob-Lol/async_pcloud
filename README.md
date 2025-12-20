# async_pcloud - Async python API client for PCloud

this in an indirect fork of https://github.com/tomgross/pcloud/

[![Package test status](https://github.com/Noob-Lol/async_pcloud/actions/workflows/python-package.yml/badge.svg)](https://github.com/Noob-Lol/async_pcloud/actions)
[![PyPI version](https://img.shields.io/pypi/v/async_pcloud.svg)](https://pypi.org/project/async_pcloud)

## Difference
It's async, uses aiohttp. I plan to reimplement all functions, and add extra - implement some of the NotImplemented, make useful combinations.

update: pcloud has too many methods, i won't implement all of them

## why i made this?
because i have not found any async packages for pcloud

## Installation
```sh
# install from PyPI
pip install async_pcloud
```

## Examples
there are 2 ways to use the AsyncPyCloud.

1. manual connect, disconnect (needed for session, because this is async):
```py
import asyncio
from async_pcloud import AsyncPyCloud
pcloud = AsyncPyCloud("token", endpoint="api")

async def main():
    await pcloud.connect()
    data = await pcloud.listfolder(folderid=0)
    print(data)
    # when you're done
    await pcloud.disconnect()

asyncio.run(main())
```

2. async with - auto connect, disconnect:
```py
pcloud = AsyncPyCloud("token")

async def main():
    async with pcloud:
    # 'async with AsyncPyCloud("token") as pcloud:' will also work
        data = await pcloud.listfolder(folderid=0)
        print(data)
```

## Class arguments
- AsyncPyCloud
  - token - the api token, you can generate one with get_auth()
  - endpoint - can be 'api' or 'eapi', choose the one used by your account
  - folder - base folder name, will be added before the path param
  - headers - you can make custom user agent or something
