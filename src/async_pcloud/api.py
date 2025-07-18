import aiohttp
from async_pcloud.validate import RequiredParameterCheck

class PyCloudAsync:
    """Simple async wrapper for PCloud API."""
    endpoints = {
        "api": "https://api.pcloud.com/",
        "eapi": "https://eapi.pcloud.com/",
    }

    def __init__(self, token, endpoint="api"):
        self.token = token
        if endpoint not in self.endpoints:
            raise ValueError("Endpoint (%s) not found. Use one of: %s", endpoint, ",".join(self.endpoints.keys()),)
        else:
            self.endpoint = self.endpoints.get(endpoint)
        self.session = None
    
    async def connect(self):
        """Creates a session, must be called before any requests."""
        self.session = aiohttp.ClientSession(base_url=self.endpoint, timeout=aiohttp.ClientTimeout(10))

    async def disconnect(self):
        if not self.session: return
        await self.session.close()
        self.session = None

    def change_token(self, token):
        self.token = token

    def _fix_path(self, path: str):
        if not path.startswith("/"): path = "/" + path
        return path
    
    async def _do_request(self, url, auth=True, method = "GET", data = None, params: dict={}, **kwargs) -> dict:
        if not self.token and auth: raise Exception("PCloud token is missing.")
        if not self.session: raise Exception("Not connected to PCloud API, call connect() first.")
        params.update(kwargs)
        if auth: params['auth'] = self.token
        if params.get('path'): params['path'] = self._fix_path(params['path'])
        async with self.session.request(method, url, data=data, params=params) as response:
            response_json = await response.json()
            if response_json["result"] != 0:
                raise Exception(f"Failed to {method} '{url}': code: {response_json['result']}, error: {response_json.get('error', 'Unknown error')}")
            return response_json
        
    async def _default_get(self, url, **kwargs):
        if not self.session: raise Exception("Not connected to PCloud API, call connect() first.")
        r = await self.session.get(url, **kwargs)
        return await r.read()
        
    async def getdigest(self):
        resp = await self._do_request("getdigest", False)
        return bytes(resp["digest"], "utf-8")
    
    async def userinfo(self, **kwargs):
        return await self._do_request("userinfo", **kwargs)
        
    async def get_pcloud_token(self, email, password, verbose=False):
        """Logs into pCloud and returns the token."""
        response = await self.userinfo(auth=False, params={'getauth': 1, 'username': email, 'password': password})
        token = response['auth']
        if verbose: print(token)
        return token

    @RequiredParameterCheck(("path", "folderid"))
    async def listfolder(self, **kwargs):
        return await self._do_request("listfolder", **kwargs)
    
    @RequiredParameterCheck(("path", "fileid"))
    async def getfilelink(self, **kwargs) -> str:
        """Returns a link to the file. Or the file's bytes if download=True."""
        file_url = await self._do_request("getfilelink", **kwargs)
        download_url = 'https://' + file_url['hosts'][0] + file_url['path']
        return download_url
    
    async def get_all_links(self, fileid: int):
        return await self._do_request("getfilelink", params={'fileid': fileid})

    async def get_file(self, file: str, folder: str):
        files = await self.listfolder(path=folder)
        file_info = next((f for f in files.get('metadata', {}).get('contents', []) if f['name'] == file), None)
        if not file_info: return None
        download_url = await self.getfilelink(fileid=file_info['fileid'])
        return download_url
    
    @RequiredParameterCheck(("path", "fileid"))
    async def download_file(self, **kwargs):
        download_url = await self.getfilelink(**kwargs)
        return await self._default_get(download_url)
    
    @RequiredParameterCheck(("files", "data"))
    async def uploadfile(self, **kwargs):
        await self._do_request("uploadfile", method="POST", **kwargs)

    @RequiredParameterCheck(("path", "folderid"))
    async def upload_one_file(self, filename: str, content: str | bytes, **kwargs):
        data = aiohttp.FormData()
        data.add_field('filename', content, filename=filename)
        await self.uploadfile(data=data, **kwargs)

    async def search(self, query: str, **kwargs):
        return await self._do_request('search', params={'query': query, **kwargs})
    
    async def stat(self, **kwargs):
        return await self._do_request("stat", **kwargs)
    
    async def invite(self, **kwargs):
        return await self._do_request("invite", **kwargs)

    async def userinvites(self, **kwargs):
        return await self._do_request("userinvites", **kwargs)

    async def logout(self, **kwargs):
        return await self._do_request("logout", **kwargs)

    async def listtokens(self, **kwargs):
        return await self._do_request("listtokens", **kwargs)

    async def deletetoken(self, **kwargs):
        return await self._do_request("deletetoken", **kwargs)
