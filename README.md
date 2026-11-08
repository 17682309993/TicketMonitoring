# 演唱会回流票监控（增强版）

监控大麦、猫眼、纷玩岛、票星球四个平台的**回流票**（别人退票后重新释放的余票），发现可购票立刻推送提醒。

> 本项目基于 [ThinkerWen/TicketMonitoring](https://github.com/ThinkerWen/TicketMonitoring) 二次修改，修复了原版若干会静默失败的问题，并补齐了通知、诊断与 ID 查询工具。感谢原作者。

## 相比原版做了什么

| 改动 | 说明 |
| --- | --- |
| **修正票星球 `showId` 陷阱** | 票星球同一场演出有 `showId` 与 `stdShowId` 两个 ID，接口只认前者。填错不会报「ID 无效」，而是返回 `1270 当前访客较多`，极易被误判成风控。新增 `查演出ID.py` 一条命令查出正确 ID |
| **Bark 推送重写** | 原版把中文塞在 URL 路径里且写死占位 key。改为 POST + JSON，带标题、`alarm` 提示音、`group`、`level=timeSensitive`（穿透专注模式），支持多设备与自建服务器 |
| **macOS 系统通知** | 无需任何 key，发现余票时弹窗 + 提示音，默认开启 |
| **余票明细** | 发现回流时打印「某场次 / 某票档 可购 N 张」，不再只是一句「已回流」 |
| **不再整程序崩溃** | 单条演出配置错误（token 过期、ID 填错）只跳过该条；已过截止时间的条目自动跳过 |
| **报错可读** | 接口被拒时抛出平台原始 `statusCode` 与文案，不再是 `'NoneType' object has no attribute 'get'` |
| **凭证可配置** | `auth` 段支持填自己的 Cookie / token，大麦不再强制使用原仓库内置的失效 Cookie |
| **配套工具** | `查演出ID.py`、`诊断.py`、`导入凭证.py`、`配置Bark.py`、`测试提醒.py` |

## 快速开始

```bash
git clone <本仓库地址>
cd TicketMonitoring
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt

cp config.example.json config.json          # 然后按下面说明填写
./.venv/bin/python 查演出ID.py 演出关键词     # 拿到 showId 填进 config.json
./.venv/bin/python start.py
```

macOS 用户可直接双击 `启动监控.command`：自动检查虚拟环境、开启防休眠（`caffeinate`）、启动监控。

## 配置

只需改 `config.json`（该文件已被 `.gitignore` 排除，不会误提交）：

| 字段 | 说明 |
| --- | --- |
| `monitor_list[].show_id` | 演出 ID。**票星球必须是 `showId`，不是 `stdShowId`** |
| `monitor_list[].platform` | `0`=大麦，`1`=猫眼，`2`=纷玩岛，`3`=票星球 |
| `monitor_list[].deadline` | 监控截止时间 `2026-12-31 23:59:59`，过期自动跳过 |
| `monitor_list[].interval_sec` | 轮询间隔秒数，默认 1，建议 3~5 防止被限流 |
| `notice.bark_key` | iOS [Bark](https://github.com/Finb/Bark) 推送 key，可留空 |
| `notice.macos_notify` | macOS 弹窗提醒，默认 `true` |
| `notice.email` + `SMTP` | 邮件提醒（QQ 邮箱需用授权码） |

配 Bark 一条命令搞定（会先试推，手机响了才写入配置）：

```bash
./.venv/bin/python 配置Bark.py https://api.day.app/你的key/
```

### Docker 运行

```bash
mkdir -p /etc/ticket-monitor
vim /etc/ticket-monitor/config.json   # 按 config.example.json 填写
docker run -d --restart=unless-stopped \
  -v /etc/ticket-monitor/config.json:/app/config.json \
  --name="ticket-monitor" designerwang/ticket-monitor:latest
```

## 平台支持现状（2026-11 实测）

| 平台 | 状态 | 说明 |
| --- | --- | --- |
| 票星球 | ✅ 可用 | 公开接口，无需 token / cookie |
| 猫眼 | 需 token | 抓 `wx.maoyan.com` 请求里的 `token=`，填 `auth.my.token`，数天到数周过期 |
| 大麦 | 基本不可用 | 需过滑块验证，原仓库内置 Cookie 早已失效 |
| 纷玩岛 | 未验证 | 返回 `47009 小岛现在太繁忙` |

## 常用工具

```bash
./.venv/bin/python 查演出ID.py 演出关键词        # 搜演出，打印 showId / stdShowId
./.venv/bin/python 查演出ID.py -s <showId>      # 查场次与各票档实时余票
./.venv/bin/python 诊断.py pxq <showId>         # 打印接口原始返回，判断是配置错还是被限流
./.venv/bin/python 配置Bark.py <key 或整条地址>  # 配 Bark 并试推
./.venv/bin/python 测试提醒.py                  # 测试所有通知渠道
./.venv/bin/python 推送GitHub.py                # 经 GitHub API 推送（git push 不通时用）
```

更详细的中文说明见 [使用说明.md](使用说明.md)。

## 常见问题

- **一直报 `1270 当前访客较多`**：九成是 `show_id` 填成了 `stdShowId`，用 `查演出ID.py` 重新取。
- **`22029000 服务熔断异常`**：请求过密被限流，把 `interval_sec` 调到 5~10，等几分钟再跑。
- **`22029998 / RE010028204063`**：平台侧业务状态（暂停销售、未开售），不是程序问题。
- **`git push` 报 `Recv failure: Operation timed out`**：`github.com:443` 在国内常被阻断，但 `api.github.com` 通常可用。用 `./.venv/bin/python 推送GitHub.py` 走 API 推送即可；`上传到GitHub.command` 检测到连不通会自动切换到这条路。

## 注意

程序仅供学习研究，请勿用于抢票倒卖等违法违规用途；轮询频率别调太低，避免给平台造成压力。使用后果由使用者自行承担。

原作者的分析文章：

- [看雪 · 某麦网回流票监控，sign 参数分析](https://bbs.kanxue.com/thread-279165.htm)
- [吾爱破解 · 某麦网回流票监控，sign 参数分析](https://www.52pojie.cn/forum.php?mod=viewthread&tid=1845064)
