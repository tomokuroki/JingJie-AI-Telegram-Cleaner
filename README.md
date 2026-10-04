# 净界（JingJie）

**本地 AI Telegram 频道清理器**。使用 Telethon 读取你已加入的频道/超级群组，再把频道简介和少量最近文本发送给你电脑上的 **Ollama / qwen3:8b** 做分类。

> 默认语言：中文。可在主菜单切换 English / Русский。

## 安全边界

- **完全不读取、不分析、不删除私人聊天。**
- 默认只扫描 broadcast 频道；超级群组默认关闭，可用 `SCAN_MEGAGROUPS=true` 手动开启。
- **机器人私聊也不触碰**，因为它们属于私人对话；当前版本只处理频道和超级群组。
- 如果当前账号是频道/超级群组的 **管理员或所有者**，该频道会被保护，不会退出。
- 默认先运行 **Dry Run**，只显示候选项。
- 真正退出频道时需要手动输入 `LEAVE` 二次确认。
- 真正退出前会再次检查管理员/所有者权限；无法确认权限时按安全策略保留。
- AI 完全运行在本机 Ollama。频道文本不会发送到云端 AI。

## AI 判定

模型返回 0~1 分数：

- `adult_score`：色情、露骨性内容、色情服务/链接等；
- `spam_score`：诈骗、钓鱼、批量推广、假抽奖、重复广告等；
- `junk_score`：明显自动生成/重复、低价值垃圾流；
- `normal / uncertain`：正常或不确定时保守保留。

默认阈值：

```env
ADULT_THRESHOLD=0.72
SPAM_THRESHOLD=0.82
JUNK_THRESHOLD=0.90
```

可以在 `.env` 修改。

## 1. 前置条件

### Python

建议 Python 3.11+。

### Ollama

你当前已有：

```text
qwen3:8b
```

确认 Ollama 正在运行：

```bat
ollama list
```

如果服务没启动：

```bat
ollama serve
```

### Telegram API

从 `my.telegram.org` 获取自己的 `API_ID` 和 `API_HASH`。

## 2. 安装

Windows 下双击：

```text
INSTALL.bat
```

它会创建 `.venv` 并安装依赖。

## 3. 启动

双击：

```text
RUN.bat
```

第一次启动如果 `.env` 里没有 Telegram API 配置，程序会询问并写入 `.env`。

### 如果收不到验证码

新版登录界面会明确显示验证码的发送方式：Telegram 应用内消息、SMS、登录邮箱或其他 Telegram 选择的方式。**不要只等 SMS**；Telegram 经常把登录验证码发送到你已经登录的 Telegram 客户端。程序不会保存验证码。若看到 `FloodWait`，请按显示的秒数等待后再重试。

## 4. 菜单

```text
1. 扫描频道 / 超级群组（Dry Run）
2. 扫描并退出 AI 判定的 18+ / Spam / 垃圾频道
3. 切换语言
4. 显示配置
0. 退出
```

建议第一次永远先选 `1` 看报告。

## 5. `.env`

首次安装会从 `.env.example` 复制。

关键项：

```env
APP_LANG=zh
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
RECENT_MESSAGES=12
SCAN_BROADCAST_CHANNELS=true
SCAN_MEGAGROUPS=false
PROTECT_ADMINS=true
SAFE_USERNAMES=
SAFE_IDS=
```

如果有永远不能退出的频道，可加入白名单：

```env
SAFE_USERNAMES=important_channel,my_team
SAFE_IDS=123456789,987654321
```

## 6. 报告

每次扫描在 `logs/` 生成：

- `scan_YYYYMMDD_HHMMSS.json`
- `scan_YYYYMMDD_HHMMSS.csv`

报告记录 AI 分数、动作、原因和错误，不会记录 Telegram 登录验证码。

---

## English quick start

1. Run `INSTALL.bat`.
2. Make sure `ollama list` shows `qwen3:8b`.
3. Run `RUN.bat`.
4. Enter your own Telegram `API_ID` / `API_HASH` on first launch.
5. Use menu item **1** first for a Dry Run.
6. Private chats and bot DMs are never scanned or deleted. Broadcast channels are scanned by default; supergroups are opt-in.
7. Admin/owner channels are protected.

## Русский — быстрый старт

1. Запусти `INSTALL.bat`.
2. Проверь, что `ollama list` показывает `qwen3:8b`.
3. Запусти `RUN.bat`.
4. При первом запуске введи свои Telegram `API_ID` / `API_HASH`.
5. Сначала выбирай пункт **1** — Dry Run.
6. Личные чаты и диалоги с ботами не анализируются и не удаляются. По умолчанию сканируются только broadcast-каналы; супергруппы включаются отдельно.
7. Каналы/супергруппы, где аккаунт админ или владелец, защищены.

### Если код не приходит

Программа теперь явно пишет, куда Telegram отправил код: **в приложение Telegram, SMS, email или другим выбранным Telegram способом**. Не жди только SMS — очень часто код приходит служебным сообщением в уже авторизованный Telegram. Код нигде не сохраняется. Если появится `FloodWait`, подожди указанное число секунд и только потом пробуй снова.

## 项目结构

```text
JingJie_AI_Telegram_Cleaner/
├─ main.py
├─ config.py
├─ i18n.py
├─ models.py
├─ ollama_ai.py
├─ telegram_cleaner.py
├─ requirements.txt
├─ .env.example
├─ INSTALL.bat
├─ RUN.bat
├─ data/
├─ logs/
└─ README.md
```
