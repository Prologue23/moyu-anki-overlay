#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

rm -f moyu_debug.log
rm -rf .git

git init -b main
git config user.name "zoeyzhang233666"
git config user.email "zoeyzhang233666@users.noreply.github.com"

git add .gitignore README.md __init__.py overlay.py review_controller.py \
  config_dialog.py config.json config.md manifest.json

git commit -m "$(cat <<'EOF'
Initial release: Moyu Anki Overlay (摸鱼复习条)

Desktop pill bar for stealth Anki reviews with hover/keyboard grading and GUI settings.
EOF
)"

# Prefer gh if available
if command -v gh >/dev/null 2>&1; then
  if ! gh auth status >/dev/null 2>&1; then
    echo "请先登录 GitHub CLI："
    echo "  gh auth login"
    exit 1
  fi
  gh repo create zoeyzhang233666/moyu-anki-overlay --public --source=. --remote=origin --push \
    --description "摸鱼复习条：桌面胶囊式 Anki 复习插件" \
    || {
      git remote remove origin 2>/dev/null || true
      git remote add origin "https://github.com/zoeyzhang233666/moyu-anki-overlay.git"
      git push -u origin main
    }
else
  echo "未检测到 gh。将使用 git push。"
  echo "请先在浏览器创建空仓库：https://github.com/new"
  echo "  Owner: zoeyzhang233666"
  echo "  Repository name: moyu-anki-overlay"
  echo "  不要勾选 Add a README"
  read -r -p "创建好后按回车继续推送…" _
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/zoeyzhang233666/moyu-anki-overlay.git"
  git push -u origin main
fi

echo
echo "完成：https://github.com/zoeyzhang233666/moyu-anki-overlay"
