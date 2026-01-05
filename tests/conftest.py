import json
import logging

import aiohttp
import pytest
from aiohttp import web
from anyio import Path, open_file

log = logging.getLogger("async_pcloud")
log.setLevel(logging.DEBUG)
PORT = 5023


@pytest.fixture
async def start_mock_server():
    BASE_DIR = Path(__file__).parent
    DATA_DIR = str(BASE_DIR / "data")

    async def generic_get_handler(request: web.Request):
        method = request.path.lstrip("/").split("?")[0]
        file_path = BASE_DIR / "data" / f"{method}.json"
        safepath = str(file_path)
        query = request.query_string
        log.debug(f"Processing Method: {method}, query: {query}")
        if method == "gettextfile":
            return web.Response(text="this isnt json", status=200)
        if not safepath.startswith(DATA_DIR) or not await Path(safepath).exists():
            if query == "auth=TOKEN":
                # default pass for get methods
                return web.json_response({"result": 0, "pass": "true"}, status=200)
            return web.json_response({"Error": "Path not found or not accessible!"}, status=404)
        async with await open_file(safepath, encoding="utf-8") as f:
            try:
                content = await f.read()
                content = json.loads(content)
            except json.JSONDecodeError:
                return web.Response(text="Invalid JSON file", status=500)
        return web.json_response(content)

    async def generic_post_handler(request: web.Request):
        reader = await request.multipart()
        field = await reader.next()
        log.debug(f"Field type: {type(field)}")
        if not isinstance(field, aiohttp.BodyPartReader):
            return web.json_response({"error": "Expected BodyPartReader"}, status=400)
        if field.name != "file":
            return web.json_response({"error": "Expected field 'file'"}, status=400)
        file_content = await field.read()
        size = len(file_content)
        log.debug(f"File size: {size}")
        return web.json_response({
            "result": 0,
            "metadata": {"size": size},
        })

    app = web.Application()

    # GET: /someendpoint -> load tests/data/someendpoint.json
    app.router.add_route("GET", "/{tail:.*}", generic_get_handler)
    # POST: /someupload -> parse multipart upload
    app.router.add_route("POST", "/{tail:.*}", generic_post_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", PORT)
    await site.start()
    log.debug(f"Started mock server on http://localhost:{PORT}")
    yield
    log.debug("Shutting down server...")
    await runner.cleanup()
