"""Persist only BYYT cookies; Windows encrypts them for the current user with DPAPI."""

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path

from requests.cookies import RequestsCookieJar, create_cookie


class Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, decrypt=False):
    if os.name != "nt":
        raise OSError("当前仅支持 Windows DPAPI 加密会话存储。")
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(ctypes.cast(output.pbData, ctypes.c_void_p))


def save_session(path: Path, cookies):
    records = [{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path,
                "secure": c.secure, "expires": c.expires, "rest": c._rest}
               for c in cookies if c.domain.lstrip(".") == "byyt.ustb.edu.cn"]
    if not records:
        raise OSError("未取得教务系统 Cookie，会话未保存。")
    encrypted = protect(json.dumps(records).encode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(encrypted)
    temporary.replace(path)


def load_session(path: Path):
    jar = RequestsCookieJar()
    if path.exists():
        for record in json.loads(protect(path.read_bytes(), decrypt=True)):
            if record["domain"].lstrip(".") == "byyt.ustb.edu.cn":
                jar.set_cookie(create_cookie(**record))
    return jar
