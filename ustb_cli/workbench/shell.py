"""工作台命令循环；业务处理器由应用层注册。"""

import shlex

from .terminal import TerminalUI


def update_auth_status(ui, command, result):
    if command == "status":
        ui.status = {0: "会话有效", 1: "未登录或会话已失效", 130: "状态未验证"}.get(result, "状态检查失败")
    elif result == 0:
        ui.status = "未登录" if command == "logout" else "会话有效"


def workbench(state_dir, parse_command):
    """Interactive shell; each feature returns here after completion."""
    ui = TerminalUI(state_dir)
    ui.welcome()
    print("\n正在检查登录状态……", flush=True)
    status_args = parse_command(["--state-dir", str(state_dir), "auth", "status"])
    update_auth_status(ui, "status", status_args.handler(status_args))
    aliases = {"1": "/login", "2": "/status", "3": "/logout", "0": "/exit",
               "exit": "/exit", "quit": "/exit", "help": "/help", "?": "/help"}
    while True:
        try:
            choice = ui.read_command().strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出工作台。")
            return 0
        choice = aliases.get(choice, choice)
        if not choice:
            continue
        if choice == "/exit":
            print("已退出工作台。")
            return 0
        if choice in ("/help", "/"):
            ui.help()
            continue
        if choice == "/clear":
            ui.clear()
            continue
        try:
            parts = shlex.split(choice)
        except ValueError:
            print(ui.paint("  命令引号未闭合，请重新输入。", "38;5;203"))
            continue
        if not parts or parts[0] not in ("/login", "/status", "/logout", "/grades", "/ranks"):
            print(ui.paint("  未识别的命令。输入 /help 查看可用功能。", "38;5;203"))
            continue
        try:
            command = ([parts[0][1:]] if parts[0] in ("/grades", "/ranks") else ["auth", parts[0][1:]])
            args = parse_command(["--state-dir", str(state_dir), *command, *parts[1:]])
        except SystemExit:
            continue  # A malformed feature command must not close the workbench.
        print()
        result = args.handler(args)
        if args.group in ("grades", "ranks"):
            if result == 0:
                ui.status = "会话有效"
            elif result == 1:
                ui.status = "会话已失效"
        if args.group == "auth":
            update_auth_status(ui, args.command, result)
