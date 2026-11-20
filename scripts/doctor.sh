#!/usr/bin/env bash
# Environment check + idempotent install of the AI Video Editor toolchain (macOS/Homebrew; no sudo).
#   scripts/doctor.sh          # check only
#   scripts/doctor.sh --fix    # install anything missing
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
FIX=${1:-}; ok=0
check() { if eval "$2" >/dev/null 2>&1; then printf "  ✓ %-22s %s\n" "$1" "$(eval "$3" 2>/dev/null | head -1)"; else printf "  ✗ %-22s missing\n" "$1"; ok=1; [ "$FIX" = "--fix" ] && eval "$4"; fi; }
echo "System: $(uname -sm) $(sw_vers -productVersion 2>/dev/null) | $(sysctl -n machdep.cpu.brand_string 2>/dev/null) | $(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 )) GB"
check node      "command -v node"   "node --version"                 "brew install node@22"
check ffmpeg    "command -v ffmpeg" "ffmpeg -version | head -1 | cut -d' ' -f1-3" "brew install ffmpeg"
check yt-dlp    "command -v yt-dlp" "yt-dlp --version"               "brew install yt-dlp"
check uv        "command -v uv"     "uv --version"                   "brew install uv"
check python-venv "test -x .venv/bin/python" ".venv/bin/python --version" "uv venv .venv --python 3.12"
check whisper   ".venv/bin/python -c 'import whisper'" "echo openai-whisper" "uv pip install --python .venv/bin/python -r requirements.txt"
check opencv    ".venv/bin/python -c 'import cv2; assert cv2.CascadeClassifier'" ".venv/bin/python -c 'import cv2;print(cv2.__version__)'" "uv pip install --python .venv/bin/python -r requirements.txt"
check remotion  "test -d engine/node_modules/remotion" "cd engine && node -p \"require('remotion/package.json').version\"" "(cd engine && npm ci)"
check hyperframes "test -f .claude/skills/hyperframes/scripts/plugin-cli.mjs" "scripts/hf --version 2>/dev/null | tail -1" "npx -y skills add heygen-com/hyperframes --agent claude-code --skill hyperframes --skill hyperframes-cli --skill media-use -y"
check remotion-skills "test -e .claude/skills/remotion-best-practices" "echo installed" "npx -y skills add remotion-dev/skills --agent claude-code --all -y"
check sfx-kit   "test -f styles/assets/sfx/whoosh.wav" "ls styles/assets/sfx | tr '\n' ' '" "scripts/make_sfx.sh"
echo "  HW encode: $(ffmpeg -hide_banner -encoders 2>/dev/null | grep -o 'h264_videotoolbox' | head -1 || echo none)  | Torch MPS: $(.venv/bin/python -c 'import torch;print(torch.backends.mps.is_available())' 2>/dev/null)"
[ $ok = 0 ] && echo "✓ toolchain ready" || echo "✗ missing pieces (run scripts/doctor.sh --fix)"
exit $ok
