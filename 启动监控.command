#!/bin/bash
# 演唱会回流票监控 —— 启动脚本（macOS 下可双击运行）
cd "$(dirname "$0")" || exit 1

PY=".venv/bin/python"

if [ ! -x "$PY" ]; then
  echo "未找到虚拟环境 .venv，正在重新创建..."
  python3 -m venv .venv && .venv/bin/python -m pip install -q -r requirements.txt || {
    echo "环境创建失败，请手动执行： python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
    read -r _
    exit 1
  }
fi

echo "=========================================="
echo " 演唱会回流票监控已启动"
echo " 提示：运行期间请勿关闭此窗口（可最小化）"
echo " 已启用防休眠：电脑闲置不会睡，屏幕可以正常黑屏"
echo " 注意：合上盖子仍会睡眠并暂停监控"
echo " 停止监控：按 Ctrl + C"
echo "=========================================="

if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -i -s "$PY" start.py
else
  "$PY" start.py
fi

echo
echo "监控已结束，按回车键关闭窗口。"
read -r _
