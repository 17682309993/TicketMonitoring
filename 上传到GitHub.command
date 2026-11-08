#!/bin/bash
# 把本项目上传到 GitHub（双击运行）
# 首次运行会打开浏览器让你授权，之后只需确认仓库名
set -u
cd "$(dirname "$0")" || exit 1

pause() { echo; printf "按回车键关闭窗口…"; read -r _; }

echo "=========================================="
echo " 上传「演唱会回流票监控」到 GitHub"
echo "=========================================="
echo

# ---------- 1. 检查仓库状态 ----------
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "✗ 当前目录不是 git 仓库。"
  pause; exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "· 还有未提交的改动，先提交一次…"
  git add -A
  git commit -q -m "chore: 更新说明与配置示例" || true
fi

# ---------- 2. 安全检查：凭证绝不能上传 ----------
if git ls-files --error-unmatch config.json >/dev/null 2>&1; then
  echo "✗ 检测到 config.json 已被纳入版本管理！"
  echo "  里面含 Bark key / Cookie 等凭证，绝不能上传。已中止。"
  echo "  修复：git rm --cached config.json  然后重新运行本脚本。"
  pause; exit 1
fi
if git log --all --pretty=format: --name-only | grep -qx "config.json"; then
  echo "✗ 历史提交里出现过 config.json，直接推送会泄露凭证。已中止。"
  echo "  请先在终端执行：git rm --cached config.json 并重建历史，或告诉我来处理。"
  pause; exit 1
fi
echo "✓ 检查通过：config.json 与 .venv 都不在提交范围"

# ---------- 3. 登录 GitHub ----------
if ! gh auth status >/dev/null 2>&1; then
  echo
  echo "还没登录 GitHub，接下来会打开浏览器授权（只需一次）。"
  echo "浏览器页面里输入终端显示的 8 位代码，点 Authorize 即可。"
  echo
  if ! gh auth login --hostname github.com --git-protocol https --web; then
    echo "✗ 登录失败，可稍后重试。"
    pause; exit 1
  fi
fi

USER_NAME=$(gh api user --jq .login 2>/dev/null)
if [ -z "$USER_NAME" ]; then
  echo "✗ 拿不到 GitHub 账号信息，请检查网络或重新登录。"
  pause; exit 1
fi
echo "✓ 已登录：$USER_NAME"

# ---------- 4. 仓库名与可见性 ----------
echo
DEFAULT_NAME="TicketMonitoring"
printf "仓库名（直接回车 = %s）：" "$DEFAULT_NAME"
read -r REPO_NAME
REPO_NAME=${REPO_NAME:-$DEFAULT_NAME}

echo "可见性：1) 公开（所有人可看）  2) 私有（只有你能看）"
printf "选择 1 或 2（直接回车 = 2 私有）："
read -r VIS
case "${VIS:-2}" in
  1) VIS_FLAG="--public";  WANT_PRIVATE="false" ;;
  *) VIS_FLAG="--private"; WANT_PRIVATE="true"  ;;
esac

# ---------- 5. 创建仓库并关联远程 ----------
FULL="$USER_NAME/$REPO_NAME"
echo
if ! gh repo view "$FULL" >/dev/null 2>&1; then
  echo "· 正在创建仓库 $FULL …"
  gh repo create "$FULL" $VIS_FLAG \
    --description "演唱会回流票监控（大麦/猫眼/纷玩岛/票星球），支持 Bark 推送" \
    || { echo "✗ 创建仓库失败"; pause; exit 1; }
fi

# 可见性以你的选择为准（不依赖 gh 参数是否生效）
CUR_PRIV=$(gh api "repos/$FULL" --jq .private 2>/dev/null)
if [ -n "$CUR_PRIV" ] && [ "$CUR_PRIV" != "$WANT_PRIVATE" ]; then
  if gh api -X PATCH "repos/$FULL" -F private="$WANT_PRIVATE" >/dev/null 2>&1; then
    if [ "$WANT_PRIVATE" = "false" ]; then echo "· 仓库已设为公开"; else echo "· 仓库已设为私有"; fi
  fi
fi

ORIGIN_WANT="https://github.com/$FULL.git"
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$ORIGIN_WANT"
else
  git remote add origin "$ORIGIN_WANT"
fi

# ---------- 6. 推送：git 不通时自动改走 API ----------
echo "· 正在推送代码…"
CAN_GIT=0
nc -z -G 5 github.com 443 >/dev/null 2>&1 && CAN_GIT=1

if [ "$CAN_GIT" = "1" ] && GIT_HTTP_LOW_SPEED_LIMIT=1000 GIT_HTTP_LOW_SPEED_TIME=20 git push -u origin main 2>/dev/null; then
  echo "✓ 推送完成（git）"
else
  if [ "$CAN_GIT" = "1" ]; then
    echo "! git push 被拒绝或中断，改用 GitHub API 推送…"
  else
    echo "! github.com:443 连不通（国内网络常见），改走 GitHub API 推送…"
  fi
  PY="$PWD/.venv/bin/python"
  [ -x "$PY" ] || PY=$(command -v python3)
  "$PY" 推送GitHub.py --repo "$FULL" || { echo "✗ 推送失败，请检查网络后重试"; pause; exit 1; }
fi

URL="https://github.com/$USER_NAME/$REPO_NAME"
echo
echo "=========================================="
echo " ✓ 上传完成：$URL"
echo "=========================================="
echo
echo "注意：config.json 未上传（含你的 Bark key），别人克隆后需"
echo "      cp config.example.json config.json 再填自己的配置。"
open "$URL" 2>/dev/null
pause
