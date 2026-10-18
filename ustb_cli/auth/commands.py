"""认证业务的命令注册与执行。"""

from io import BytesIO
import sys
import webbrowser

from PIL import Image, UnidentifiedImageError
import requests

from .client import AuthClient, AuthError
from .qr import print_qr
from .session import load_session, save_session


def register_commands(subparsers):
    auth = subparsers.add_parser("auth", help="登录与会话管理")
    auth.set_defaults(handler=run_auth)
    commands = auth.add_subparsers(dest="command", required=True)
    login = commands.add_parser("login", help="微信/企业微信扫码登录")
    login.add_argument("--timeout", type=int, default=180, help="等待扫码秒数，默认 180")
    login.add_argument("--open", action="store_true", help="在浏览器打开本地二维码图片")
    login.add_argument("--no-terminal-qr", action="store_true", help="仅保存二维码图片")
    commands.add_parser("status", help="向教务系统验证会话")
    commands.add_parser("logout", help="清除本地会话")


def run_auth(args):
    session_path = args.state_dir / "session.bin"
    qr_path = args.state_dir / "login-qr.png"
    try:
        if args.command == "logout":
            session_path.unlink(missing_ok=True)
            qr_path.unlink(missing_ok=True)
            print("已清除本地会话。")
            return 0
        if args.command == "status" and not session_path.is_file():
            print("尚未登录，请输入 /login 扫码登录。")
            return 1
        client = AuthClient()
        if args.command == "status":
            client.session.cookies.update(load_session(session_path))
            if client.is_authenticated():
                print("已登录，教务会话有效。")
                return 0
            print("未登录或会话已失效，请选择登录或运行 cli.exe auth login。")
            return 1
        print("正在访问教务系统并获取统一认证二维码……", flush=True)
        challenge = client.start()
        args.state_dir.mkdir(parents=True, exist_ok=True)
        # Normalize the server image to PNG regardless of its original encoding.
        Image.open(BytesIO(challenge.image)).save(qr_path, format="PNG")
        print("请使用微信或企业微信扫码，并在手机上确认登录。", flush=True)
        print(f"二维码图片：{qr_path.resolve()}", flush=True)
        if not args.no_terminal_qr:
            print_qr(challenge.image)
        if args.open:
            webbrowser.open(qr_path.resolve().as_uri())
        client.poll(challenge, args.timeout,
                    on_scanned=lambda: print("已扫码，请在手机上确认……", flush=True),
                    on_authorized=lambda: print("手机已授权，正在完成教务系统登录……", flush=True))
        save_session(session_path, client.session.cookies)
        print("登录成功，已加密保存教务会话。")
        return 0
    except KeyboardInterrupt:
        print("\n已取消登录。", file=sys.stderr)
        return 130
    except requests.RequestException:
        # Request exception messages may contain auth codes and session identifiers.
        print("网络请求失败，请检查网络后重试。", file=sys.stderr)
        return 2
    except (AuthError, OSError, ValueError, UnidentifiedImageError) as exc:
        print(f"操作失败：{exc}", file=sys.stderr)
        return 2
    finally:
        if args.command == "login":
            qr_path.unlink(missing_ok=True)
