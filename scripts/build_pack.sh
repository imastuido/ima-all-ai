#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

slug="$(
python3 - <<'PY'
import json
from pathlib import Path

meta_path = Path("_meta.json")
if meta_path.exists():
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    slug = meta.get("slug")
    if slug:
        print(slug)
        raise SystemExit(0)

clawhub_path = Path("clawhub.json")
clawhub = json.loads(clawhub_path.read_text(encoding="utf-8"))
name = clawhub.get("name")
if not name:
    raise SystemExit("Unable to resolve slug from _meta.json or clawhub.json")
print(name)
PY
)"

pack_root="$REPO_ROOT/pack"
target_dir="$pack_root/$slug"

root_files=(
  "!keywords.txt"
  "CHANGELOG.md"
  "README.md"
  "SECURITY.md"
  "SKILL.md"
  "_meta.json"
  "clawhub.json"
  "requirements.txt"
)

root_dirs=(
  "scripts"
  "references"
  "capabilities"
)

rm -rf "$pack_root"
mkdir -p "$target_dir"

for file in "${root_files[@]}"; do
  [[ -f "$file" ]] || {
    echo "Missing required file: $file" >&2
    exit 1
  }
  cp "$file" "$target_dir/"
done

for dir in "${root_dirs[@]}"; do
  [[ -d "$dir" ]] || {
    echo "Missing required directory: $dir" >&2
    exit 1
  }
  cp -R "$dir" "$target_dir/"
done

rm -f "$target_dir/references/operations/live-smoke-history.md"

find "$target_dir" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$target_dir" -type d \( -name ".pytest_cache" -o -name ".venv" -o -name ".idea" \) -prune -exec rm -rf {} +
find "$target_dir" -type f \( -name "*.pyc" -o -name ".DS_Store" \) -delete

if [[ -d "$target_dir/tooling" ]]; then
  echo "Pack unexpectedly contains tooling/; this pack should stay runtime-only." >&2
  exit 1
fi

echo "Created pack at: $target_dir"
