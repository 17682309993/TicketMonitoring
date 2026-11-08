#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把本项目打包成可上传到 Skill 市场的 zip

要点：
- 只打包 git 已跟踪的文件（config.json、.venv、.git 天然排除）
- 压缩包内统一放在 ticket-monitoring/ 目录下，保证根目录有 SKILL.md
- 中文文件名显式标记 UTF-8（zip 的 general purpose bit 11），否则解压会变乱码
- 保留 .command / .py 的可执行权限

用法：
    ./.venv/bin/python 打包Skill.py                 # 输出到 ../ticket-monitoring.zip
    ./.venv/bin/python 打包Skill.py -o ~/Desktop/x.zip
"""

import argparse
import os
import subprocess
import sys
import zipfile

CWD = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = "ticket-monitoring"


def tracked_files():
    r = subprocess.run(["git", "ls-files", "-z"], cwd=CWD, capture_output=True)
    if r.returncode != 0:
        sys.exit("读取 git 索引失败")
    return [p for p in r.stdout.decode("utf-8").split("\0") if p]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default=os.path.join(os.path.dirname(CWD), "ticket-monitoring.zip"))
    ap.add_argument("--flat", action="store_true",
                    help="不套 ticket-monitoring/ 目录，SKILL.md 直接位于 zip 顶层（平台把 zip 根当包根时用）")
    args = ap.parse_args()
    out = os.path.abspath(os.path.expanduser(args.output))
    prefix = "" if args.flat else SKILL_DIR

    st = subprocess.run(["git", "status", "--porcelain"], cwd=CWD, capture_output=True, text=True)
    if st.stdout.strip():
        print("! 有未提交的改动，压缩包只会包含已提交的内容：")
        print(st.stdout.rstrip())
        print()

    names = tracked_files()
    if "SKILL.md" not in names:
        sys.exit("✗ SKILL.md 还没提交，请先 git add SKILL.md && git commit")
    if "config.json" in names:
        sys.exit("✗ config.json 被 git 跟踪了，里面含 Bark key，先 git rm --cached config.json")

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    if os.path.exists(out):
        os.remove(out)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        if prefix:
            top = zipfile.ZipInfo(prefix + "/", date_time=(1980, 1, 1, 0, 0, 0))
            top.external_attr = (0o40755 << 16) | 0x10
            z.writestr(top, b"")
        for rel in names:
            full = os.path.join(CWD, rel)
            if not os.path.isfile(full):
                continue
            with open(full, "rb") as f:
                data = f.read()
            arcname = f"{prefix}/{rel}" if prefix else rel
            zi = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
            mode = 0o755 if (os.access(full, os.X_OK) or rel.endswith(".command")) else 0o644
            zi.external_attr = mode << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            # 非 ASCII 文件名必须打 UTF-8 标记，否则解压乱码
            zi.flag_bits |= 0x800
            z.writestr(zi, data)

    # 自检
    with zipfile.ZipFile(out) as z:
        items = z.namelist()
        bad_utf8 = [i.filename for i in z.infolist()
                    if not i.filename.isascii() and not (i.flag_bits & 0x800)]
    files = [i for i in items if not i.endswith("/")]
    leaks = [i for i in items if i.endswith("/config.json") or "/.venv/" in i or "/.git/" in i]
    skill_md = f"{prefix}/SKILL.md" if prefix else "SKILL.md"
    if prefix:
        bad_root = [i for i in items if not i.startswith(prefix + "/")]
    else:
        bad_root = [i for i in items if "/" in i.rstrip("/")]
    has_cjk = [n for n in files if not n.isascii()]

    print(f"输出：{out}")
    print(f"大小：{os.path.getsize(out) / 1024:.1f} KB，{len(files)} 个文件")
    print(f"{'✓' if skill_md in items else '✗'} SKILL.md 位于包根目录（{skill_md}）")
    print(f"{'✓' if not leaks else '✗'} 无 config.json / .venv / .git" + (f" → {leaks}" if leaks else ""))
    print(f"{'✓' if not bad_root else '✗'} 包内无多余层级" + (f" → {bad_root}" if bad_root else ""))
    print(f"{'✓' if not bad_utf8 else '✗'} 中文文件名已标记 UTF-8（共 {len(has_cjk)} 个）" + (f" → {bad_utf8}" if bad_utf8 else ""))

    ok = (skill_md in items) and not leaks and not bad_root and not bad_utf8
    if not ok:
        sys.exit("✗ 自检未通过")
    print("\n用这个 zip 去 Skill 市场「更换 / 上传」即可。")


if __name__ == "__main__":
    main()
