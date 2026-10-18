"""Small, dependency-free terminal shell with Windows line editing."""

import ctypes
import os
from pathlib import Path
import shutil
import sys
import unicodedata
from itertools import groupby

COMMANDS = ("/login", "/status", "/logout", "/grades", "/ranks", "/help", "/clear", "/exit")

USTB_LOGO = (
    "██╗   ██╗███████╗████████╗██████╗ ",
    "██║   ██║██╔════╝╚══██╔══╝██╔══██╗",
    "██║   ██║███████╗   ██║   ██████╔╝",
    "██║   ██║╚════██║   ██║   ██╔══██╗",
    "╚██████╔╝███████║   ██║   ██████╔╝",
    " ╚═════╝ ╚══════╝   ╚═╝   ╚═════╝ ",
)


def cells(text):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def clip(text, width):
    result = ""
    for char in text:
        if cells(result + char) > width:
            break
        result += char
    return result


class TerminalUI:
    def __init__(self, state_dir):
        self.state_dir = state_dir
        self.color = bool(sys.stdout.isatty() and not os.environ.get("NO_COLOR"))
        if self.color and os.name == "nt":
            kernel = ctypes.windll.kernel32
            kernel.GetStdHandle.restype = ctypes.c_void_p
            handle = kernel.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            kernel.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
            kernel.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            self.color = bool(kernel.GetConsoleMode(handle, ctypes.byref(mode)) and
                              kernel.SetConsoleMode(handle, mode.value | 4))
        self.editing = bool(self.color and os.name == "nt" and sys.stdin.isatty())
        self.history = []  # Commands stay in memory; never record login secrets on disk.
        self.status = "本地会话待验证" if (state_dir / "session.bin").exists() else "未登录"

    @property
    def width(self):
        return max(20, min(shutil.get_terminal_size((88, 24)).columns - 2, 96))

    def paint(self, text, code="38;5;173"):
        return f"\033[{code}m{text}\033[0m" if self.color else text

    def rule(self):
        print(self.paint("─" * self.width, "38;5;240"))

    def welcome(self):
        width = self.width
        print()
        title = " USTB CLI · v0.1 "
        if width < 44:
            print(self.paint("USTB CLI", "1;38;5;173"))
            print(clip("北京科技大学 · 教务工作台", width))
        else:
            print(self.paint("╭─" + title + "─" * (width - cells(title) - 3) + "╮"))
            def panel_row(text, logo=False):
                line = clip(text, width - 4)
                if logo:
                    rendered = "".join(self.paint("".join(group), "1;38;5;215" if face else "38;5;130")
                                       for face, group in groupby(line, key=lambda c: c == "█"))
                else:
                    rendered = line
                print(self.paint("│") + " " + rendered + " " * (width - cells(line) - 3) + self.paint("│"))

            panel_row("")
            inset = " " * max(0, (width - 4 - max(cells(row) for row in USTB_LOGO)) // 2)
            for row in USTB_LOGO:
                panel_row(inset + row, logo=True)
            panel_row("")
            for text in ("北京科技大学 · 教务工作台", "",
                         "扫码登录 · 必修加权成绩 · 课程排名", "输入 /login 开始，输入 /help 查看命令", ""):
                panel_row(" " * max(0, (width - 4 - cells(text)) // 2) + text)
            print(self.paint("╰" + "─" * (width - 2) + "╯"))
        print(self.paint("  工作区  ", "38;5;244") + clip(str(Path.cwd()), width - 10))
        print(self.paint("  /login", "38;5;173") + " 扫码登录    " +
              self.paint("/status", "38;5;173") + " 登录状态    " +
              self.paint("/help", "38;5;173") + " 帮助" if width >= 60 else clip("  /login 登录  /help 帮助", width))

    def help(self):
        print("\n" + self.paint("  可用命令", "1"))
        for command, description in (
            ("/login", "微信 / 企业微信扫码登录"),
            ("/login --open", "在浏览器打开二维码图片"),
            ("/status", "向教务系统验证会话"),
            ("/logout", "清除本地登录会话"),
            ("/grades", "查询主修必修课加权成绩及明细"),
            ("/grades --year 2025-2026", "按学年计算，可追加 --term 1"),
            ("/ranks", "查询课程成绩排名和总人数"),
            ("/ranks 高数", "搜索名称、课程代码，支持常用简称"),
            ("/ranks 数学 Ⅱ", "多个关键词须全部匹配"),
            ("/ranks 线性代数 --exact", "精确匹配完整课程名或代码"),
            ("/ranks --year 2025-2026", "按学年查询，可追加 --term 1 或 --json"),
            ("/clear", "清屏并重新显示工作台"),
            ("/help", "显示命令帮助"),
            ("/exit", "退出工作台，保留登录会话"),
        ):
            print("  " + self.paint(command.ljust(28)) + description)
        print(self.paint("\n  兼容数字快捷键：1 登录 · 2 状态 · 3 退出登录 · 0 退出", "38;5;244"))

    def clear(self):
        if self.color:
            print("\033[2J\033[H", end="")
        self.welcome()

    def read_command(self):
        print()
        self.rule()
        print("  " + self.paint("●", "38;5;114" if self.status == "会话有效" else "38;5;244") +
              " " + self.status + self.paint("  ·  统一认证", "38;5;244"))
        if self.editing:
            print(self.paint("  / 命令  ·  Tab 补全  ·  ↑↓ 历史  ·  Ctrl+C 退出", "38;5;244"))
            return self._windows_input()
        return input(self.paint("❯ ", "1;38;5;173"))

    def _windows_input(self):
        import msvcrt

        text, position = "", 0
        history_index, draft = len(self.history), ""
        matches, completion_index = [], -1

        def redraw():
            # Show a horizontal window around the cursor on small terminals.
            available = self.width - 3
            start = 0
            while cells(text[start:position]) >= available:
                start += 1
            visible = clip(text[start:], available)
            print("\r\033[2K" + self.paint("❯ ", "1;38;5;173") + visible, end="")
            print(f"\r\033[{2 + cells(text[start:position])}C", end="", flush=True)

        redraw()
        while True:
            key = msvcrt.getwch()
            if key in ("\r", "\n"):
                print()
                if text.strip():
                    self.history.append(text)
                return text
            if key == "\x03":
                raise KeyboardInterrupt
            if key == "\x04" and not text:
                raise EOFError
            if key in ("\x00", "\xe0"):
                special = msvcrt.getwch()
                if special in ("H", "P"):
                    if history_index == len(self.history):
                        draft = text
                    history_index = max(0, min(len(self.history), history_index + (-1 if special == "H" else 1)))
                    text = self.history[history_index] if history_index < len(self.history) else draft
                    position = len(text)
                elif special == "K":
                    position = max(0, position - 1)
                elif special == "M":
                    position = min(len(text), position + 1)
                elif special == "G":
                    position = 0
                elif special == "O":
                    position = len(text)
                elif special == "S":
                    text = text[:position] + text[position + 1:]
                matches = []
            elif key == "\t":
                if not matches:
                    matches = [c for c in COMMANDS if c.startswith(text)]
                    completion_index = -1
                if matches:
                    completion_index = (completion_index + 1) % len(matches)
                    text = matches[completion_index]
                    position = len(text)
            else:
                matches = []
                if key == "\b" and position:
                    text = text[:position - 1] + text[position:]
                    position -= 1
                elif key == "\x1b":
                    text, position = "", 0
                elif key.isprintable():
                    text = text[:position] + key + text[position:]
                    position += 1
            redraw()
