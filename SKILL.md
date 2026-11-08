---
name: ticket-monitoring
description: 演唱会回流票监控工具集。用于监控大麦、猫眼、纷玩岛、票星球四个平台的余票（别人退票后重新释放的「回流票」），发现可购票立即通过 Bark 推送、macOS 通知或邮件告警。当用户提到演唱会/球赛等演出抢票、回流票、余票监控、缺票登记，或需要查询演出 showId、配置演出监控、排查票星球 1270/22029000 等接口报错、配置 Bark 推送时使用本技能。
agent_created: true
---

# 演唱会回流票监控

监控四个票务平台的余票，售罄后一旦有人退票释放，立刻推送提醒。核心思路：轮询余票接口，发现 `canBuyCount > 0` 即判定回流。

## 何时使用

- 用户想监控某场演出的回流票 / 余票 / 缺票登记
- 需要把演出页链接或名称换算成可用的 `showId`
- 监控报错，需要判断是「配置错」「凭证过期」还是「被接口限流」
- 需要配置 Bark / macOS 通知 / 邮件提醒

## 目录结构

```
ticket-monitoring/
├── SKILL.md                # 本文件
├── start.py                # 主程序：读 config.json，多线程轮询
├── Monitor.py              # 基类：配置加载、Bark 推送、macOS 通知
├── Monitor_PXQ.py          # 票星球（唯一稳定可用的平台）
├── Monitor_DM.py           # 大麦
├── Monitor_MY.py           # 猫眼（需 token）
├── Monitor_FWD.py          # 纷玩岛
├── email_notifier.py       # 邮件通知
├── config.example.json     # 配置模板（复制为 config.json 后填写）
├── 查演出ID.py              # 按关键词搜演出，打印 showId / stdShowId
├── 诊断.py                  # 打印接口原始返回，定位报错层级
├── 配置Bark.py              # 写入 Bark key 并试推
├── 测试提醒.py              # 测试全部通知渠道
├── 导入凭证.py              # 从浏览器 Copy as cURL 导入 Cookie / token
├── 推送GitHub.py            # 走 GitHub API 推送（git push 不通时用）
└── 使用说明.md              # 完整中文说明，需要细节时读这个
```

## 快速开始

1. 建虚拟环境并装依赖：

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```

2. 生成配置：

```bash
cp config.example.json config.json
```

3. 取演出 ID（**这一步最容易错，见下方「关键陷阱」**）：

```bash
./.venv/bin/python 查演出ID.py 演出关键词
```

4. 把 `show_id`、`show_name`、`platform`、`deadline` 填进 `config.json` 的 `monitor_list`：

| 字段 | 说明 |
| --- | --- |
| `show_id` | 平台演出 ID，**必须用 `showId`，不是 `stdShowId`** |
| `platform` | `1` 大麦 / `2` 猫眼 / `3` 票星球 / `4` 纷玩岛 |
| `deadline` | 停止监控时间，格式 `2026-11-08 15:30:00`，过期条目自动跳过 |
| `interval_sec` | 轮询间隔，默认 3 秒；出现限流报错就调到 5~10 |

5. 起监控：

```bash
./.venv/bin/python start.py
```

发现回流时终端打印场次 / 票档 / 张数，并同时触发 Bark 推送与 macOS 通知。

## 关键陷阱：showId 与 stdShowId

票星球同一场演出有两个 ID：

| 字段 | 用途 |
| --- | --- |
| `showId`（如 `697834bc1203fa00012dede1`） | ✅ 场次与余票接口必须用它 |
| `stdShowId`（如 `697834bc1203fa00012deddf`） | ❌ 网页链接 / 分享链接里常见，接口不认 |

传 `stdShowId` 时接口返回 `1270 当前访客较多`，**看起来完全像反爬风控，实际是 ID 错了**。这是本技能最容易误判的地方——遇到 `1270` 先换 ID，不要去做 Cookie、指纹、浏览器自动化。

## 配置提醒渠道

```bash
./.venv/bin/python 配置Bark.py https://api.day.app/你的key/   # 试推成功后写入配置
./.venv/bin/python 测试提醒.py                                # 复测所有渠道
```

Bark 用 POST JSON 发送，带 `level: timeSensitive`，能穿透专注模式。`notice.macos_notify` 设为 `false` 可关掉桌面弹窗。

## 报错对照表

| 现象 | 判断 |
| --- | --- |
| `1270 当前访客较多` | `show_id` 填成了 `stdShowId`，用 `查演出ID.py` 重取 |
| `22029000 服务熔断异常` | 请求过密被限流，`interval_sec` 调大到 5~10，等几分钟 |
| `22029998 / RE010028204063` | 平台侧业务状态（暂停销售 / 未开售），不是程序问题 |
| `'NoneType' object has no attribute 'get'` | 旧版代码的报错，接口未返回 `data`；已改为打印平台原始状态码 |
| 加载失败但 ID 看着没错 | 跑 `./.venv/bin/python 诊断.py pxq <showId>` 看原始返回 |

## 平台现状（2026-11 实测）

| 平台 | 状态 |
| --- | --- |
| 票星球 | ✅ 公开接口，无需 token / cookie / 签名 |
| 猫眼 | 需在 `auth.my.token` 填小程序抓包得到的 token，会过期 |
| 大麦 | 需过滑块验证，基本不可用；`auth.dm.cookie` 需填自己的 |
| 纷玩岛 | 未验证，返回 `47009 太繁忙` |

## 安全要求

**绝不能提交或分享 `config.json`**——它含 Bark key 和登录凭证。仓库里已用 `.gitignore` 排除，只提交 `config.example.json`。推送到 GitHub 时必须先确认 `git ls-files` 里没有 `config.json`。

## 更多细节

配置字段全表、抓包取 ID 的步骤、Bark 与 QQ 邮箱授权码的配置方式、各平台实测记录，见 `使用说明.md`。
