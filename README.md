# USTB CLI

`cli.exe` 是整个教务工作台的总入口。采用带暖橙色标识、会话状态和命令输入区的终端界面，现已支持扫码登录、主修必修课加权成绩计算和课程成绩排名查询。

## 使用（Windows）

源码仓库不包含 `cli.exe`。首次使用请安装 Python 3.10+，在项目目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m ustb_cli
```

源码运行时，可将下文命令中的 `.\cli.exe` 替换为 `.\.venv\Scripts\python.exe -m ustb_cli`。按下文构建步骤生成可执行文件后，也可直接运行：

```powershell
.\cli.exe
```

也可以双击项目根目录的 `cli.exe`。进入后输入斜杠命令：

```text
╭─ USTB CLI · v0.1 ───────────────────────────╮
│     ██╗   ██╗███████╗████████╗██████╗       │
│     ██║   ██║██╔════╝╚══██╔══╝██╔══██╗     │
│     ██║   ██║███████╗   ██║   ██████╔╝     │
│     ██║   ██║╚════██║   ██║   ██╔══██╗     │
│     ╚██████╔╝███████║   ██║   ██████╔╝     │
│      ╚═════╝ ╚══════╝   ╚═╝   ╚═════╝      │
│          北京科技大学 · 教务工作台         │
╰────────────────────────────────────────────╯
  ● 未登录 · 统一认证
❯ /login
```

`/login` 扫码登录，`/status` 检查登录，`/logout` 清除本地会话，`/help` 查看帮助，`/clear` 清屏，`/exit` 退出工作台。Windows 交互终端支持 Tab 命令补全、↑↓ 历史、左右方向键编辑和 Esc 清空输入；Ctrl+C 退出工作台，在扫码过程中则取消当前登录并回到输入区。

每项功能结束后返回命令输入区。关闭工作台保留会话。启动工作台后自动检查一次登录状态：存在本地会话时联网验证，没有会话时直接提示登录；检查失败或取消后仍可进入工作台。状态栏显示验证结果，`/status` 可随时手动刷新，`/clear` 不会重复触发检查。直接执行 `auth`、`grades` 或 `ranks` 子命令时不会额外检查一次。保留数字 `1/2/3/0` 快捷键。窄终端自动简化布局；重定向输出或设置 `NO_COLOR` 时不使用界面颜色。

需要脚本调用时，使用同一入口的子命令：

```powershell
.\cli.exe auth login
.\cli.exe auth status
.\cli.exe auth logout
```

登录默认在终端显示二维码，同时生成 PNG 图片，使用微信或企业微信扫码并在手机确认。二维码过期、等待超时或 Ctrl+C 取消后可重新运行命令。图片在登录结束后清除。

```powershell
# 终端太窄时，在浏览器打开本地二维码图片
.\cli.exe auth login --open --no-terminal-qr
# 等待扫码 5 分钟
.\cli.exe auth login --timeout 300
# 将会话放在指定目录（全局参数位于 auth 之前）
.\cli.exe --state-dir .local auth login
```

默认保存到 `%USERPROFILE%\.ustb-cli\session.bin`。仅保存教务域名 Cookie，使用 Windows DPAPI 按当前 Windows 用户加密，不持久化 SSO/微信认证 Cookie。`logout` 清除本地会话；已建立的服务端会话由学校管理。

## 必修加权成绩

登录后，在工作台输入 `/grades`，或直接运行：

```powershell
.\cli.exe grades
.\cli.exe grades --year 2025-2026 --term 1
.\cli.exe grades --json
```

程序复用本地登录会话，通过 `/user/me` 取得查询上下文，再 POST JSON 到 `/cjgl/grcjcx/grcjcx`，自动分页获取完整成绩。学年学期筛选在本地按响应的 `xnxq` / `xnxqmc` 完成（学校接口单独传学年曾返回空列表）。默认不限制学年学期，`--year` 必须为连续两年，例如 `2023-2024`。

公式为 **Σ(必修课总评成绩 × 学分) / Σ(必修课学分)**。采用 `kcxz=必修`、`zzcj` 总评、`xf` 学分，默认排除明确标记为辅修的记录。使用 Decimal 计算，最终均分四舍五入保留两位小数；数值不及格和 0 分计入。

输出纳入课程及贡献、总学分、加权总分、均分和排除原因。等级成绩（如优、良）、未出分、无有效学分、性质缺失等不猜测换算；有这些待核对项时标记“部分结果”。没有可计算课程时不输出 0 分。相同课程代码与修读身份下存在多条记录时，默认全部排除并提示核对；可用 `/grades --repeat all` 明确按全部考试记录计算，届时同一课程学分会重复计入。此计算口径为本地统计，不等于校方已确认的重修或综合成绩口径。

`--json` 输出包含规则、筛选条件、UTC 抓取时间和明细，精确数值以字符串表示。成绩仅在本次运行的内存和终端输出中使用，不自动保存成绩文件。接口格式、分页数量或查询失败时停止计算；退出码 0 表示查询计算完成（可能含待核对项），1 表示需要登录，2 表示查询失败，130 表示取消。

请求与字段依据：[BeikeSchedule 成绩请求实现](https://github.com/coderirse/BeikeSchedule/blob/260d091e53d7886ee7d1a46525849344ff1c7bd5/app/src/main/assets/import/jw_grades.js)、[接口字段说明](https://github.com/coderirse/BeikeSchedule/blob/260d091e53d7886ee7d1a46525849344ff1c7bd5/docs/JWXT_API.md)。学校接口更新后可能需要调整适配。

## 课程成绩排名

登录后输入 `/ranks`，或通过子命令查询：

```powershell
.\cli.exe ranks
.\cli.exe ranks --year 2025-2026 --term 1
.\cli.exe ranks --json
.\cli.exe ranks 高数
.\cli.exe ranks 数学 Ⅱ --year 2025-2026 --term 1
.\cli.exe ranks MATH101 --exact --json
```

按照 [ustb-grade-rank-extension 的提取方法](https://github.com/napnah/ustb-grade-rank-extension/blob/main/content-script.js)，直接读取成绩接口 `/cjgl/grcjcx/grcjcx` 的 `pm`（排名）与 `zrs`（总人数），同时显示课程代码、名称、学期和总评成绩。复用已有登录会话、完整分页检查和本地学年学期筛选，不需要安装浏览器扩展。

查询包含必修、选修等接口返回的全部课程记录，同课多次考试逐条保留。排名按各条记录直接提取，避免同名课程或重修记录互相覆盖；排名范围以学校返回为准，不推算班级、专业或年级排名。接口未返回排名或总人数时，终端显示“未提供”，JSON 为 `null`；有值时按字符串保留。没有成绩时输出空结果，不将其视为第 0 名。

`--json` 同时包含筛选条件、UTC 抓取时间、记录总数、有排名条数、字段不完整条数及课程明细。成绩只用于本次运行，不自动落盘。登录要求、网络错误处理与退出码沿用 `grades`。

搜索可直接使用 `/ranks 高数`、`/ranks 数学 Ⅱ` 或 `/ranks MATH101`。默认按名称或代码的片段匹配，忽略大小写、空白、标点和全半角差异，支持高数（高等数学）、线代（线性代数）、大物（大学物理）、大英（大学英语）、概统（概率论与数理统计 / 概率统计）。多个关键词要求全部匹配同一条课程记录，可以分别匹配名称和代码；含空格的名称可用引号包围。`--exact` 要求关键词与完整名称或代码相等（仍忽略大小写、空白、标点和全半角），不扩展简称。

搜索在完整分页和学年学期筛选后于本地执行，保留全部匹配的考试记录。JSON 的 `queried_count` 表示当前学年学期下搜索前的条数，`course_count` 表示匹配条数；使用搜索时 `filters.search` 保存关键词，`filters.match` 为 `fuzzy` 或 `exact`。无匹配时正常返回空结果并提示调整关键词。

## 开发与构建（Python 3.10+）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[build]"
.\scripts\build.ps1
```

构建始终更新项目根目录的 `cli.exe`，可独立运行，不需要用户安装 Python。脚本先在 `.local/release/` 构建并检查启动，成功后自动关闭路径为本项目 `cli.exe` 的运行进程，再原子替换入口并校验文件哈希；旧版保留为 `.local/release/cli.previous.exe`。更新时当前 CLI 窗口会关闭，请在构建结束后重新打开 `cli.exe`。构建或启动检查失败时保留原入口。构建中间文件放在 `.local/build/`。若在沙箱中运行，可能需要批准在沙箱外执行脚本，才能识别并关闭桌面上运行的 CLI。

源码运行入口为 `python cli.py` 或 `python -m ustb_cli`，也支持相同子命令。保留原 `ustb` 命令作为兼容入口。

项目结构：

```text
cli.exe                  用户总入口（构建产物）
cli.py                   源码启动器
build.ps1                兼容原构建命令的转发入口
pyproject.toml           依赖、安装入口及打包配置
scripts/
  build.ps1              Windows 构建实现
ustb_cli/
  __main__.py            python -m ustb_cli 启动入口
  app.py                 业务命令装配、全局参数、执行分发
  auth/                  认证业务
    commands.py          auth 子命令定义及登录/状态/退出流程
    client.py            学校 SSO、扫码轮询、回调与会话验证
    session.py           本地 Cookie 加密存取
    qr.py                认证二维码终端显示
  grades/                成绩业务
    commands.py          成绩命令、会话复用与结果输出
    client.py            用户上下文与成绩分页查询
    calculator.py        必修筛选、Decimal 加权与排除说明
    ranking.py           课程排名字段提取与终端输出
    search.py            课程名称、代码搜索与常用简称匹配
  workbench/             交互工作台
    shell.py             斜杠命令循环、执行结果与状态提示
    terminal.py          USTB 立体字、界面渲染、输入编辑与补全
```

`docs/`、`tests/`、`业务.md`、`.local/`、`.venv/` 和构建产物仅在本地保留，不提交到源码仓库。

## 接口依据

实际入口和协议取自学校公开页面（2026-10-18）：

1. `https://byyt.ustb.edu.cn/` → `/oauth/login/code`。
2. SSO `/idp/authn/queryAuthMethods` 确认 `microQr`。
3. `/idp/authn/getMicroQr` → SIS `/connect/qrpage`。
4. `/connect/qrimg?sid=…` 获取原始二维码；`/connect/state?sid=…` 长轮询。
5. 状态 `2` 已扫码、`4` 等待超时可继续、`1` 手机确认成功、`3` 或大于 `200` 已过期；其他状态报错。
6. 成功后携带一次性凭据跟随学校回调，必要时提交隐藏认证表单，再通过教务 `/user/me` 验证。

这些是当前网页使用的接口，学校更新页面后可能需要调整解析。已通过本人手机扫码完成实际登录并验证教务会话。学校 SSO 回调中出现的 HTTP 重定向会在发出请求前升级为同一已知学校主机的 HTTPS 地址；异常跳转报错隐藏授权参数。当前会话持久化仅支持 Windows。
