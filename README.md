# anyrouter status page

一个最小可迁移的 anyrouter 状态页项目：

- Flask 应用：`app.py`（托管静态页 + 内置定时探测）
- 静态页面：`docs/`
- 探测脚本：`scripts/check_anyrouter.py`
- GitHub Actions 模板：`.github/workflows/status-check.yml`（可选的外部触发方案）

## 功能

- 每次探测按当前 Claude Code CLI 的关键字段格式请求 anyrouter，`max_tokens=1`
- 记录：
  - HTTP status code
  - 是否成功吐出文本
  - 最近错误消息
  - 最近探测耗时
- `app.py` 内置后台调度线程，按 `CHECK_INTERVAL_SECONDS` 周期性探测
- 支持通过 `ANYROUTER_PROXY` / `HTTPS_PROXY` / `HTTP_PROXY` 走代理访问上游
- 历史只保留最近 7 天，按小时聚合

## 本地运行

1. 复制配置文件：

   ```bash
   cp .env.example .env
   ```

2. 填入：

   - `ANYROUTER_API_BASE`
   - `ANYROUTER_API_KEY`
   - `ANYROUTER_MODEL`（推荐：`claude-opus-4-7[1m]`）
   - `CHECK_INTERVAL_SECONDS`（秒，设为 0 关闭内置调度）
   - 可选：`ANYROUTER_PROXY`、`HOST`、`PORT`

3. 安装依赖：

   ```bash
   pip install -r requirements.txt
   ```

4. 启动服务（同时托管页面并在后台周期性探测）：

   ```bash
   python app.py
   ```

   然后访问 `http://127.0.0.1:8000/`。

   如果只想跑一次探测而不启动 Web 服务：

   ```bash
   python scripts/check_anyrouter.py
   ```

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `ANYROUTER_API_BASE` | 上游 API 基础地址 |
| `ANYROUTER_API_KEY` | 上游 API Key |
| `ANYROUTER_MODEL` | 模型名，带 `[1m]` 后缀会启用 1M beta header |
| `ANYROUTER_TIMEOUT` | 单次请求超时（秒），默认 30 |
| `ANYROUTER_PROMPT` | 自定义探测提示词 |
| `ANYROUTER_PROXY` | 代理地址；未设置时会 fallback 到 `HTTPS_PROXY` / `HTTP_PROXY` |
| `HOST` / `PORT` | Flask 绑定地址，默认 `127.0.0.1:8000` |
| `CHECK_INTERVAL_SECONDS` | 内置调度间隔，`0` 表示关闭 |
| `CHECK_ON_STARTUP` | 启动时是否立即跑一次，默认 `true` |

## 部署

推荐方式：把项目部署到任意能常驻运行的机器 / 容器（自 host、VPS、Railway、Fly 等），直接运行 `python app.py`，Web 服务和调度由同一个进程完成。

如需仅部署静态页，可将 `docs/` 交给 GitHub Pages / Cloudflare Pages，并通过外部方式（GitHub Actions、Cloudflare Worker 定时器）调用 `scripts/check_anyrouter.py` 生成 `docs/data/` 下的状态文件。`.github/workflows/status-check.yml` 提供了 workflow_dispatch 模板。

## 说明

- GitHub 只识别仓库根目录下的 `.github/workflows/`；当前目录里的 workflow 是迁移模板。
- 探测失败时脚本仍会写入状态文件；只有缺少配置或写文件失败时才会退出非零。
- Flask debug reloader 下的父进程不会启动调度线程，避免重复触发。

## Opus 4.7[1m] 兼容说明

旧脚本模拟的 Claude Code 请求格式已经过时。在当前 anyrouter / new-api 链路上，旧格式容易触发 `500 new_api_panic`，真实 Claude Code CLI 请求则可以正常返回 `200`。

和旧脚本相比，当前 CLI 的关键变化主要是：

- 删除了旧参数：`temperature`
- 增加了新字段：
  - `thinking: {"type": "adaptive"}`
  - `output_config: {"effort": "medium"}`
  - `context_management`
- 增加了 Claude Code 风格的 billing/system 信息，以及更新后的 `anthropic-beta`
- `[1m]` 只用于启用 1M beta header，实际发出的 `model` 会去掉 `[1m]`

脚本现在已经按这套格式同步，探测仍保持最小开销：`max_tokens=1`、`tools=[]`、`stream=false`。

## 🚩 友情链接

感谢 **LinuxDo** 社区的支持！

[![LinuxDo](https://img.shields.io/badge/社区-LinuxDo-blue?style=for-the-badge)](https://linux.do/)

## 致敬

- [lsdefine/GenericAgent](https://github.com/lsdefine/GenericAgent)
  - 本项目中模拟 Claude Code CLI 发送请求的方式参考了这个项目。
