#!/bin/bash
# 一键推送到 https://github.com/zoeyzhang233666/moyu-anki-overlay
set -euo pipefail
cd "$(dirname "$0")"

echo "==> 本地仓库状态"
git status -sb
git log -1 --oneline

echo
echo "==> 请先用浏览器创建空仓库（若尚未创建）："
echo "    https://github.com/new"
echo "    Owner: zoeyzhang233666"
echo "    Repository name: moyu-anki-overlay"
echo "    Public"
echo "    不要勾选 Add a README / .gitignore / license"
echo
read -r -p "仓库建好后按回车开始推送…" _

git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/zoeyzhang233666/moyu-anki-overlay.git"

echo "==> 推送到 origin/main …"
git push -u origin main

echo
echo "✅ 完成：https://github.com/zoeyzhang233666/moyu-anki-overlay"
