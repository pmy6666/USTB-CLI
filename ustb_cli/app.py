"""应用入口：装配业务命令、解析参数并选择交互或直接执行。"""

import argparse
from pathlib import Path
import sys

from .auth.commands import register_commands as register_auth_commands
from .grades.commands import register_commands as register_grades_commands
from .workbench.shell import workbench


def build_parser():
    parser = argparse.ArgumentParser(prog="cli.exe", description="北京科技大学教务工作台")
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".ustb-cli", help="本地会话目录")
    groups = parser.add_subparsers(dest="group")
    register_auth_commands(groups)
    register_grades_commands(groups)
    return parser


def parse_args(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.group == "auth" and args.command == "login" and args.timeout <= 0:
        parser.error("--timeout 必须大于 0")
    return args


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    if args.group is None:
        return workbench(args.state_dir, parse_args)
    return args.handler(args)
