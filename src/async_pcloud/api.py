import aiohttp, logging, sys
from async_pcloud.validate import RequiredParameterCheck

logger = logging.getLogger('async_pcloud')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stderr)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

class PyCloudAsync:
    """Simple async wrapper for PCloud API."""
    endpoints = {
        "api": "https://api.pcloud.com/",
        "eapi": "https://eapi.pcloud.com/",
    }

    def __init__(self, token, endpoint="eapi"):
        self.token = token
        if endpoint not in self.endpoints:
            raise ValueError("Endpoint (%s) not found. Use one of: %s", endpoint, ",".join(self.endpoints.keys()),)
        else:
            self.endpoint = self.endpoints.get(endpoint)
        self.session = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()
    
    async def connect(self):
        """Creates a session, must be called before any requests."""
        self.session = aiohttp.ClientSession(base_url=self.endpoint, timeout=aiohttp.ClientTimeout(10))
        logger.debug("Connected to PCloud API")

    async def disconnect(self):
        if not self.session: return
        await self.session.close()
        logger.debug("Disconnected from PCloud API")
        self.session = None

    def change_token(self, token):
        self.token = token

    def _fix_path(self, path: str):
        if not path.startswith("/"): path = "/" + path
        return path
    
    def redact_auth(self, data: dict):
        if 'auth' in data: data['auth'] = '***'
        return data
    
    async def _do_request(self, url, auth=True, method = "GET", data = None, params: dict={}, not_found_ok=False, **kwargs) -> dict:
        if not self.token and auth: raise Exception("PCloud token is missing.")
        if not self.session: raise Exception("Not connected to PCloud API, call connect() first.")
        params.update(kwargs)
        if auth: params['auth'] = self.token
        if params.get('path'): params['path'] = self._fix_path(params['path'])
        logger.debug(f"Request: {method} {url} {self.redact_auth(params.copy())}")
        async with self.session.request(method, url, data=data, params=params) as response:
            response_json = await response.json()
            logger.debug(f"Response: {response_json} {response.status} {response.reason}")
            if response_json["result"] != 0:
                error = response_json.get('error', 'Unknown error')
                if not_found_ok and 'not found' in error: return {}
                raise Exception(f"Failed to {method} '{url}': code: {response_json['result']}, error: {error}")
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
        """Logs into pCloud and returns the token. Also prints it if verbose."""
        response = await self.userinfo(auth=False, params={'getauth': 1, 'username': email, 'password': password})
        token = response['auth']
        if verbose: print(token)
        return token

    @RequiredParameterCheck(("path", "folderid"))
    async def listfolder(self, **kwargs):
        return await self._do_request("listfolder", **kwargs)
    
    @RequiredParameterCheck(("path", "fileid"))
    async def getfilelink(self, **kwargs) -> str:
        """Returns a link to the file."""
        file_url = await self._do_request("getfilelink", **kwargs)
        if not file_url: return ''
        download_url = 'https://' + file_url['hosts'][0] + file_url['path']
        return download_url
    
    async def get_all_links(self, fileid: int):
        return await self._do_request("getfilelink", params={'fileid': fileid})
    
    @RequiredParameterCheck(("path", "fileid"))
    async def download_file(self, **kwargs):
        download_url = await self.getfilelink(**kwargs)
        if not download_url: return
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
