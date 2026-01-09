import json
from hashlib import sha1
from typing import ClassVar

import aiohttp
from anyio import Path

from .exceptions import ApiError, NoSessionError, NoTokenError
from .utils import __version__, log, to_api_datetime
from .validate import MODE_AND, RequiredParameterCheck


class AsyncPyCloud:
    """Simple async wrapper for PCloud API."""
    endpoints: ClassVar = {
        "api": "https://api.pcloud.com/",
        "eapi": "https://eapi.pcloud.com/",
        "test": "http://localhost:5023/",
    }

    def __init__(self, token, endpoint="eapi", folder=None, headers=None, session=None):
        self.token = token
        self.folder = folder
        self.headers = headers or {"User-Agent": f"async_pcloud/{__version__}"}
        self.__version__ = __version__
        valid_endpoint = self.endpoints.get(endpoint)
        if not valid_endpoint:
            msg = f"Endpoint ({endpoint}) not found. Use one of: {', '.join(self.endpoints.keys())}"
            raise ValueError(msg)
        self.endpoint = valid_endpoint
        self._provide_session = session is None
        if session:
            session = self._get_session()
            self.session = session
            self.headers.update(session.headers)
        else:
            self.session = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()

    async def connect(self):
        """Creates a session, must be called before any requests."""
        if not self.session and self._provide_session:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(10), raise_for_status=True)
            log.debug("Connected.")
        else:
            log.debug("Session already exists.")

    async def disconnect(self):
        if self.session and self._provide_session:
            await self.session.close()
            log.debug("Disconnected.")
            self.session = None
        else:
            log.debug("No session to disconnect.")

    def change_token(self, new_token):
        self.token = new_token

    def set_session(self, session: aiohttp.ClientSession):
        self.session = session
        self.headers.update(session.headers)
        self._provide_session = False
        log.debug("Session set.")

    def _get_session(self):
        if self.session is None:
            raise NoSessionError
        if not isinstance(self.session, aiohttp.ClientSession):
            msg = "session must be an aiohttp.ClientSession"
            raise TypeError(msg)
        return self.session

    def _fix_path(self, path: str):
        if not path.startswith("/"):
            path = "/" + path
        if self.folder:
            path = f"/{self.folder}{path}"
        return path.removesuffix("/")

    @staticmethod
    def _redact_auth(data: dict):
        # this is genius
        data_copy = data.copy()
        if "auth" in data_copy:
            data_copy["auth"] = "***"
        return data_copy

    def _prepare_params(self, params=None, *, auth=True, **kwargs):
        """Converts kwargs to params, and does auth check."""
        if params is None:
            params = {}
        new_params = {**params, **kwargs}
        if not self.token and auth:
            raise NoTokenError
        if auth and not new_params.get("auth"):
            new_params["auth"] = self.token
        if new_params.get("path"):
            new_params["path"] = self._fix_path(new_params["path"])
        return new_params

    async def _do_request(self, url: str, method="GET", data=None, params=None, *, auth=True, **kwargs):
        if params is None:
            params = {}
        session = self._get_session()
        params = self._prepare_params(params, auth=auth, **kwargs)
        log.debug("Request: %s %s %s", method, url, self._redact_auth(params))
        # add endpoint
        url = self.endpoint + url
        async with session.request(method, url, data=data, params=params, headers=self.headers) as response:
            response.raise_for_status()
            response_json: dict = await response.json()
            log.debug("Response: %s %d %s", response_json, response.status, response.reason)
            return response_json

    async def _get_text(self, url: str, params=None, *, auth=True, not_found_ok=False, **kwargs):
        if params is None:
            params = {}
        session = self._get_session()
        params = self._prepare_params(params, auth=auth, **kwargs)
        log.debug("Request: GET (text) %s %s", url, self._redact_auth(params))
        async with session.get(self.endpoint + url, params=params, headers=self.headers) as response:
            response.raise_for_status()
            log.debug("Response: %d %s", response.status, response.reason)
            text = await response.text()
        try:
            j = json.loads(text)
        except json.JSONDecodeError:
            return text
        if j.get("error"):
            log.debug("Bad response: %s", j)
            if not_found_ok and "not found" in j["error"]:
                return None
            raise ApiError(j["error"])
        return text

    async def _default_get(self, url, **kwargs):
        session = self._get_session()
        async with session.get(url, **kwargs) as response:
            response.raise_for_status()
            return await response.read()

    # Authentication stuff
    async def getdigest(self):
        resp = await self._do_request("getdigest", auth=False)
        return bytes(resp["digest"], "utf-8")

    async def get_auth(self, email: str, password: str, token_expire=31536000, *, verbose=False) -> str:
        """Logs into pCloud and returns the token. Defaults to 1 year. Also prints it if verbose."""
        digest = await self.getdigest()
        passworddigest = sha1(password.encode("utf-8") + bytes(sha1(email.encode("utf-8")).hexdigest(), "utf-8") + digest)
        params = {
            "getauth": 1,
            "username": email,
            "digest": digest.decode("utf-8"),
            "passworddigest": passworddigest.hexdigest(),
            "authexpire": token_expire,
        }
        response = await self.userinfo(auth=False, params=params)
        token = response["auth"]
        if verbose:
            print(token)
        return token

    # General
    async def userinfo(self, **kwargs):
        return await self._do_request("userinfo", **kwargs)

    async def supportedlanguages(self):
        return await self._do_request("supportedlanguages")

    @RequiredParameterCheck(("language",))
    async def setlanguage(self, **kwargs):
        return await self._do_request("setlanguage", **kwargs)

    @RequiredParameterCheck(("mail", "reason", "message"), mode=MODE_AND)
    async def feedback(self, **kwargs):
        return await self._do_request("feedback", **kwargs)

    async def currentserver(self):
        return await self._do_request("currentserver")

    async def diff(self, **kwargs):
        return await self._do_request("diff", **kwargs)

    async def getfilehistory(self, **kwargs):
        return await self._do_request("getfilehistory", **kwargs)

    async def getip(self):
        return await self._do_request("getip")

    async def getapiserver(self):
        return await self._do_request("getapiserver")

    # Folder
    @RequiredParameterCheck(("path", "folderid", "name"))
    async def createfolder(self, **kwargs):
        return await self._do_request("createfolder", **kwargs)

    @RequiredParameterCheck(("path", "folderid", "name"))
    async def createfolderifnotexists(self, **kwargs):
        return await self._do_request("createfolderifnotexists", **kwargs)

    @RequiredParameterCheck(("path", "folderid"))
    async def listfolder(self, **kwargs):
        return await self._do_request("listfolder", **kwargs)

    @RequiredParameterCheck(("path", "folderid"))
    async def renamefolder(self, **kwargs):
        return await self._do_request("renamefolder", **kwargs)

    @RequiredParameterCheck(("path", "folderid"))
    async def deletefolder(self, **kwargs):
        return await self._do_request("deletefolder", **kwargs)

    @RequiredParameterCheck(("path", "folderid"))
    async def deletefolderrecursive(self, **kwargs):
        return await self._do_request("deletefolderrecursive", **kwargs)

    @RequiredParameterCheck(("path", "folderid"))
    @RequiredParameterCheck(("topath", "tofolderid"))
    async def copyfolder(self, **kwargs):
        return await self._do_request("copyfolder", **kwargs)

    # File
    @RequiredParameterCheck(("files", "data"))
    async def uploadfile(self, **kwargs):
        # TODO: upload chunks (streaming)
        data = kwargs.get("data")
        if data:
            if isinstance(data, aiohttp.FormData):
                return await self._do_request("uploadfile", method="POST", **kwargs)
            msg = "data must be aiohttp.FormData"
            raise ValueError(msg)
        files = kwargs.pop("files", [])
        if not files:
            msg = "no data or files provided"
            raise ValueError(msg)
        if not isinstance(files, list):
            msg = "files must be a list of file paths"
            raise TypeError(msg)
        log.debug("Uploading %d files: %s", len(files), files)
        form = aiohttp.FormData()
        for file in files:
            file_path = Path(file)
            if not await file_path.exists():
                msg = f"File does not exist: {file_path}"
                raise FileNotFoundError(msg)
            filename = file_path.name
            content = await file_path.read_bytes()
            form.add_field("file", content, filename=filename)
        kwargs["data"] = form
        return await self._do_request("uploadfile", method="POST", **kwargs)

    @RequiredParameterCheck(("path", "folderid"))
    async def upload_one_file(self, filename: str, content, **kwargs):
        if not isinstance(content, bytes) and not isinstance(content, str):
            msg = "content must be bytes or str"
            raise TypeError(msg)
        data = aiohttp.FormData()
        data.add_field("filename", content, filename=filename)
        return await self.uploadfile(data=data, **kwargs)

    @RequiredParameterCheck(("progresshash",))
    async def uploadprogress(self, **kwargs):
        return await self._do_request("uploadprogress", **kwargs)

    @RequiredParameterCheck(("url",))
    async def downloadfile(self, **kwargs):
        return await self._do_request("downloadfile", **kwargs)

    @RequiredParameterCheck(("url",))
    async def downloadfileasync(self, **kwargs):
        return await self._do_request("downloadfileasync", **kwargs)

    @RequiredParameterCheck(("path", "fileid"))
    async def copyfile(self, **kwargs):
        return await self._do_request("copyfile", **kwargs)

    @RequiredParameterCheck(("path", "fileid"))
    async def checksumfile(self, **kwargs):
        return await self._do_request("checksumfile", **kwargs)

    @RequiredParameterCheck(("path", "fileid"))
    async def deletefile(self, **kwargs):
        return await self._do_request("deletefile", **kwargs)

    async def renamefile(self, **kwargs):
        return await self._do_request("renamefile", **kwargs)

    @RequiredParameterCheck(("path", "fileid"))
    async def stat(self, **kwargs):
        return await self._do_request("stat", **kwargs)

    async def search(self, query: str, **kwargs):
        """Undocumented, also supports offset and limit kwargs."""
        return await self._do_request("search", params={"query": query, **kwargs})

    # Auth
    async def sendverificationemail(self, **kwargs):
        return await self._do_request("sendverificationemail", **kwargs)

    async def verifyemail(self, **kwargs):
        return await self._do_request("verifyemail", **kwargs)

    async def changepassword(self, **kwargs):
        return await self._do_request("changepassword", **kwargs)

    async def lostpassword(self, **kwargs):
        return await self._do_request("lostpassword", **kwargs)

    async def resetpassword(self, **kwargs):
        return await self._do_request("resetpassword", **kwargs)

    async def register(self, **kwargs):
        return await self._do_request("register", **kwargs)

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

    async def sendchangemail(self, **kwargs):
        return await self._do_request("sendchangemail", **kwargs)

    async def changemail(self, **kwargs):
        return await self._do_request("changemail", **kwargs)

    async def senddeactivatemail(self, **kwargs):
        return await self._do_request("senddeactivatemail", **kwargs)

    async def deactivateuser(self, **kwargs):
        return await self._do_request("deactivateuser", **kwargs)

    # Streaming
    @staticmethod
    def _make_link(response: dict, *, not_found_ok=False):
        if "not found" in response.get("error", ""):
            if not_found_ok:
                return None
            raise ApiError(response["error"])
        return f"https://{response['hosts'][0]}{response['path']}"

    @RequiredParameterCheck(("path", "fileid"))
    async def getfilelink(self, *, not_found_ok=False, **kwargs):
        """Returns a link to the file."""
        response = await self._do_request("getfilelink", **kwargs)
        return self._make_link(response, not_found_ok=not_found_ok)

    @RequiredParameterCheck(("path", "fileid"))
    async def download_file(self, *, not_found_ok=False, **kwargs):
        download_url = await self.getfilelink(not_found_ok=not_found_ok, **kwargs)
        if download_url is None:
            return None
        return await self._default_get(download_url)

    @RequiredParameterCheck(("path", "fileid"))
    async def getvideolink(self, **kwargs):
        response = await self._do_request("getvideolink", **kwargs)
        return self._make_link(response)

    @RequiredParameterCheck(("path", "fileid"))
    async def getvideolinks(self, **kwargs):
        return await self._do_request("getvideolinks", **kwargs)

    @RequiredParameterCheck(("path", "fileid"))
    async def getaudiolink(self, **kwargs):
        response = await self._do_request("getaudiolink", **kwargs)
        return self._make_link(response)

    @RequiredParameterCheck(("path", "fileid"))
    async def gethlslink(self, **kwargs):
        response = await self._do_request("gethlslink", **kwargs)
        return self._make_link(response)

    @RequiredParameterCheck(("path", "fileid"))
    async def gettextfile(self, *, not_found_ok=False, **kwargs):
        return await self._get_text("gettextfile", not_found_ok=not_found_ok, **kwargs)

    # Archiving
    @RequiredParameterCheck(("folderid", "folderids", "fileids"))
    async def getzip(self, **kwargs):
        return await self._do_request("getzip", json=False, **kwargs)

    @RequiredParameterCheck(("folderid", "folderids", "fileids"))
    async def getziplink(self, **kwargs):
        return await self._do_request("getziplink", **kwargs)

    @RequiredParameterCheck(("folderid", "folderids", "fileids"))
    @RequiredParameterCheck(("topath", "tofolderid", "toname"))
    async def savezip(self, **kwargs):
        return await self._do_request("savezip", **kwargs)

    @RequiredParameterCheck(("path", "fileid"))
    @RequiredParameterCheck(("topath", "tofolderid"))
    async def extractarchive(self, **kwargs):
        return await self._do_request("extractarchive", **kwargs)

    @RequiredParameterCheck(("progresshash",))
    async def extractarchiveprogress(self, **kwargs):
        return await self._do_request("extractarchiveprogress", **kwargs)

    @RequiredParameterCheck(("progresshash",))
    async def savezipprogress(self, **kwargs):
        return await self._do_request("savezipprogress", **kwargs)

    # Sharing
    @RequiredParameterCheck(("path", "folderid"))
    @RequiredParameterCheck(("mail", "permissions"), mode=MODE_AND)
    async def sharefolder(self, **kwargs):
        return await self._do_request("sharefolder", **kwargs)

    async def listshares(self, **kwargs):
        return await self._do_request("listshares", **kwargs)

    # Public links
    @RequiredParameterCheck(("path", "fileid"))
    async def getfilepublink(self, **kwargs):
        return await self._do_request("getfilepublink", **kwargs)

    @RequiredParameterCheck(("code", "fileid"))
    async def getpublinkdownload(self, **kwargs):
        return await self._do_request("getpublinkdownload", **kwargs)

    @RequiredParameterCheck(("path", "folderid"))
    async def gettreepublink(self, **kwargs):
        raise NotImplementedError

    @RequiredParameterCheck(("code",))
    async def showpublink(self, **kwargs):
        return await self._do_request("showpublink", auth=False, **kwargs)

    @RequiredParameterCheck(("code",))
    async def copypubfile(self, **kwargs):
        return await self._do_request("copypubfile", **kwargs)

    async def listpublinks(self, **kwargs):
        return await self._do_request("listpublinks", **kwargs)

    async def listplshort(self, **kwargs):
        return await self._do_request("listplshort", **kwargs)

    @RequiredParameterCheck(("linkid",))
    async def deletepublink(self, **kwargs):
        return await self._do_request("deletepublink", **kwargs)

    @RequiredParameterCheck(("linkid",))
    async def changepublink(self, **kwargs):
        return await self._do_request("changepublink", **kwargs)

    @RequiredParameterCheck(("path", "folderid"))
    async def getfolderpublink(self, **kwargs):
        expire = kwargs.get("expire")
        if expire is not None:
            kwargs["expire"] = to_api_datetime(expire)
        return await self._do_request("getfolderpublink", **kwargs)

    @RequiredParameterCheck(("code",))
    async def getpubzip(self, *, unzip=False, **kwargs):
        raise NotImplementedError
        # TODO: Implement this in async
        # zipresponse = self._do_request(
        #     "getpubzip", auth=False, json=False, **kwargs
        # )
        # if not unzip:
        #     return zipresponse
        # zipfmem = BytesIO(zipresponse)
        # code = kwargs.get("code")
        # try:
        #     zf = zipfile.ZipFile(zipfmem)
        # except zipfile.BadZipfile:
        #     # Could also be the case, if public link is password protected.
        #     log.warn(
        #         f"No valid zipfile found for code f{code}. Empty content is returned."
        #     )
        #     return ""
        # names = zf.namelist()
        # if names:
        #     contents = zf.read(names[0])
        # else:
        #     log.warn(f"Zip file is empty for code f{code}. Empty content is returned.")
        #     contents = ""
        # return contents

    # Trash
    async def trash_list(self, **kwargs):
        return await self._do_request("trash_list", **kwargs)

    @RequiredParameterCheck(("fileid", "folderid"))
    async def trash_restorepath(self, **kwargs):
        return await self._do_request("trash_restorepath", **kwargs)

    @RequiredParameterCheck(("fileid", "folderid"))
    async def trash_restore(self, **kwargs):
        return await self._do_request("trash_restore", **kwargs)

    @RequiredParameterCheck(("fileid", "folderid"))
    async def trash_clear(self, **kwargs):
        return await self._do_request("trash_clear", **kwargs)
