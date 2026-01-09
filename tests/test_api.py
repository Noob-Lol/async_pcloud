from pathlib import Path

import pytest

from async_pcloud import AsyncPyCloud


class DummyPyCloud(AsyncPyCloud):
    def __init__(self, token="TOKEN", endpoint="test", folder=None, headers=None):
        if headers is None:
            headers = {"User-Agent": "test_async_pcloud/0.1"}
        super().__init__(token, endpoint, folder, headers)


pc = DummyPyCloud()


def check_pass(json_data: dict):
    assert json_data.get("result") == 0 and json_data.get("pass") == "true"


@pytest.mark.asyncio
@pytest.mark.usefixtures("start_mock_server")
class TestPcloudApi:
    async def test_userinfo(self):
        async with pc:
            pc.change_token("2")
            assert pc.token == "2"
            assert await pc.getip() == {"result": 0, "ip": "127.0.0.1", "country": "idk"}
            token = await pc.get_auth("test@example.com", "password")
            assert token == "TOKEN"
            pc.change_token(token)

    async def test_upload_files(self):
        async with pc:
            testfile = Path(__file__).parent / "data" / "upload.txt"
            res = await pc.uploadfile(files=[testfile])
            assert res == {"result": 0, "metadata": {"size": 14}}

    async def test_get_files(self):
        async with pc:
            assert await pc.getfilelink(fileid=1) == "https://first.pcloud.com/verylonglink/test.txt"
            assert await pc.gettextfile(fileid=1) == "this isnt json"

    async def test_other(self):
        async with pc:
            assert await pc.currentserver() == {"result": 0, "ip": "127.0.0.1"}
            check_pass(await pc.supportedlanguages())
            check_pass(await pc.getfilehistory())
            check_pass(await pc.diff())
