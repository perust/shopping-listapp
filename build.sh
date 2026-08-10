#!/usr/bin/env bash
# index_pdf.template.html 의 플레이스홀더에 .env 의 API 키를 주입해
# 브라우저에서 바로 열 수 있는 index_pdf.html 을 생성한다.
#
#   ./build.sh
#
# 주의: 생성된 index_pdf.html 에는 API 키가 평문으로 포함된다.
#       .gitignore 에 등록되어 있으며, 외부에 공유하지 말 것.

set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "오류: .env 파일이 없습니다." >&2; exit 1; }
[ -f src/index_pdf.template.html ] || { echo "오류: src/index_pdf.template.html 이 없습니다." >&2; exit 1; }

python3 - <<'PY'
import pathlib, re, sys

env = {}
for line in pathlib.Path(".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")

key = env.get("OPENROUTER_API_KEY", "")
if not key:
    sys.exit("오류: .env 에 OPENROUTER_API_KEY 가 없습니다.")

tpl = pathlib.Path("src/index_pdf.template.html").read_text(encoding="utf-8")
if "__OPENROUTER_API_KEY__" not in tpl:
    sys.exit("오류: 템플릿에 __OPENROUTER_API_KEY__ 플레이스홀더가 없습니다.")

out = tpl.replace("__OPENROUTER_API_KEY__", key)
pathlib.Path("index_pdf.html").write_text(out, encoding="utf-8")

size = len(out.encode("utf-8"))
print(f"생성 완료: index_pdf.html ({size:,} bytes)")
print(f"주입된 키: {key[:6]}…{key[-4:]} (길이 {len(key)})")
PY
