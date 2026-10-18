"""School's microQr flow, observed from its public login scripts on 2026-10-18."""

from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
import json
import re
import time
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import requests
from PIL import Image

BYYT = "https://byyt.ustb.edu.cn"
SSO = "https://sso.ustb.edu.cn"
SIS = "https://sis.ustb.edu.cn"
ALLOWED_HOSTS = {urlsplit(u).hostname for u in (BYYT, SSO, SIS)}


class AuthError(Exception):
    pass


class QRExpired(AuthError):
    pass


def trusted_url(url):
    p = urlsplit(url)
    if (p.scheme != "https" or p.hostname not in ALLOWED_HOSTS
            or p.port not in (None, 443) or p.username or p.password):
        raise AuthError("认证跳转到了非预期地址，已停止。")
    return url


def redirect_url(url):
    """Follow legacy gateway Locations via HTTPS without sending secrets over HTTP."""
    p = urlsplit(url)
    if (p.scheme == "http" and p.hostname in ALLOWED_HOSTS
            and p.port in (None, 80) and not p.username and not p.password):
        url = p._replace(scheme="https", netloc=p.hostname).geturl()
    try:
        return trusted_url(url)
    except AuthError:
        # Query/fragment may contain one-time auth codes. Never include them in errors.
        origin = f"{p.scheme}://{p.hostname or '(无域名)'}"
        if p.port is not None:
            origin += f":{p.port}"
        raise AuthError(f"认证跳转到了非预期地址，已停止。目标：{origin}（认证参数已隐藏）") from None


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = {"action": attrs.get("action", ""),
                            "method": attrs.get("method", "get").lower(), "data": {}}
            self.forms.append(self.current)
        elif tag == "input" and self.current is not None and attrs.get("name"):
            self.current["data"][attrs["name"]] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


@dataclass(repr=False)
class Challenge:
    image: bytes = field(repr=False)
    sid: str = field(repr=False)
    appid: str = field(repr=False)
    return_url: str = field(repr=False)
    random_token: str = field(repr=False)


class AuthClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "USTB-CLI/0.1", "Accept-Language": "zh-CN,zh;q=0.9"})

    def request(self, method, url, **kwargs):
        # Validate every redirect before sending cookies or authentication codes.
        for _ in range(15):
            response = self.session.request(method, trusted_url(url),
                                            allow_redirects=False, timeout=kwargs.pop("timeout", 35), **kwargs)
            if response.status_code not in (301, 302, 303, 307, 308):
                return response
            location = response.headers.get("Location")
            if not location:
                raise AuthError("认证重定向缺少目标地址。")
            url = redirect_url(urljoin(response.url, location))
            if response.status_code == 303 or (response.status_code in (301, 302) and method.upper() == "POST"):
                method, kwargs = "GET", {}
            else:
                kwargs.pop("params", None)
        raise AuthError("认证跳转次数过多。")

    def api(self, path, data):
        r = self.request("POST", SSO + "/idp/" + path, json=data)
        r.raise_for_status()
        try:
            result = r.json()
        except ValueError:
            raise AuthError("统一认证未返回有效 JSON。") from None
        if not isinstance(result, dict) or str(result.get("code")) != "200":
            raise AuthError("统一认证接口失败，请稍后重新登录。")
        return result

    def start(self):
        self.request("GET", BYYT + "/").raise_for_status()
        r = self.request("GET", BYYT + "/oauth/login/code")
        r.raise_for_status()
        fragment = urlsplit(r.url).fragment
        q = parse_qs(fragment.partition("?")[2])
        if not q.get("lck") or not q.get("entityId"):
            raise AuthError("未取得统一认证上下文，请重新登录。")
        context = {k: q[k][0] for k in ("lck", "entityId")}
        methods = self.api("authn/queryAuthMethods", context)
        if not any("microQr" in m.get("moduleCodes", []) for m in methods.get("data", [])):
            raise AuthError("学校当前未提供微信扫码登录。")
        data = self.api("authn/getMicroQr", context).get("data", {})
        try:
            url = trusted_url(data["url"])
            params = {"appid": data["appId"], "return_url": data["returnUrl"],
                      "rand_token": data["randomToken"], "embed_flag": 1}
            page = self.request("GET", url, params=params)
            page.raise_for_status()
            page.encoding = "utf-8"
            values = {}
            for key in ("sid", "appId", "retUrl", "randToken"):
                match = re.search(r'\b' + key + r'\s*=\s*("(?:[^"\\]|\\.)*")', page.text)
                if not match:
                    raise AuthError("扫码页面格式发生变化，无法解析。")
                values[key] = unescape(json.loads(match[1]))
            trusted_url(values["retUrl"])
            image = self.request("GET", SIS + "/connect/qrimg", params={"sid": values["sid"]})
            image.raise_for_status()
            # Decode the image so an HTML error page can never be presented as a QR.
            with Image.open(BytesIO(image.content)) as im:
                im.verify()
            return Challenge(image.content, values["sid"], values["appId"],
                             values["retUrl"], values["randToken"])
        except (KeyError, TypeError, ValueError, OSError):
            raise AuthError("二维码接口返回格式异常。") from None

    def poll(self, challenge, timeout=180, on_scanned=lambda: None, on_authorized=lambda: None):
        deadline = time.monotonic() + timeout
        scanned = False
        while time.monotonic() < deadline:
            try:
                r = self.request("GET", SIS + "/connect/state", params={"sid": challenge.sid},
                                 timeout=min(35, max(1, deadline - time.monotonic())))
            except requests.Timeout:
                continue  # The school uses long polling.
            r.raise_for_status()
            try:
                state = r.json()
                code = int(state["code"])
            except (ValueError, KeyError, TypeError):
                raise AuthError("扫码状态响应异常。") from None
            if code == 1:
                if not state.get("data"):
                    raise AuthError("扫码成功但未返回认证凭据。")
                on_authorized()
                params = {"appid": challenge.appid, "auth_code": state["data"],
                          "rand_token": challenge.random_token}
                separator = "&" if "?" in challenge.return_url else "?"
                response = self.request("GET", challenge.return_url + separator + urlencode(params))
                self.complete_forms(response)
                if not self.is_authenticated():
                    raise AuthError("扫码完成，但教务会话尚未建立，请重新登录。")
                return
            if code == 2:
                if not scanned:
                    on_scanned()
                    scanned = True
            elif code == 3 or code > 200:
                raise QRExpired("二维码已过期，请重新运行登录命令。")
            elif code != 4:
                raise AuthError("扫码认证失败，请重新运行登录命令。")
            time.sleep(min(0.5, max(0, deadline - time.monotonic())))
        raise AuthError("等待扫码超时，请重新运行登录命令。")

    def complete_forms(self, response):
        # OAuth gateways may use a hidden auto-submit form between redirects.
        for _ in range(5):
            response.raise_for_status()
            parser = FormParser()
            parser.feed(response.content.decode("utf-8", errors="replace"))
            forms = [f for f in parser.forms if f["data"] and
                     any(k in f["data"] for k in ("loginToken", "SAMLResponse", "code", "ticket"))]
            if len(forms) != 1:
                return
            form = forms[0]
            url = redirect_url(urljoin(response.url, form["action"]))
            if form["method"] not in ("post", "get"):
                raise AuthError("不支持的认证回调表单。")
            response = self.request(form["method"], url,
                                    **({"data": form["data"]} if form["method"] == "post"
                                       else {"params": form["data"]}))
        raise AuthError("认证表单跳转次数过多。")

    def is_authenticated(self):
        r = self.request("POST", BYYT + "/user/me", data={})
        if r.status_code in (401, 403):
            return False
        r.raise_for_status()
        if urlsplit(r.url).hostname != "byyt.ustb.edu.cn":
            return False
        try:
            data = r.json()
        except ValueError:
            return False
        # Do not treat a 200 HTML login page or business error JSON as login success.
        if not isinstance(data, dict) or str(data.get("code", "")) in ("401", "403", "500"):
            return False
        user = data.get("data", data)
        return isinstance(user, dict) and bool(user.get("username") or user.get("userName") or user.get("yhdm"))
