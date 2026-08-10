#!/usr/bin/env bash
# NVIDIA 프록시를 켜고 요약기를 브라우저에서 연다.
#
#   ./start.sh
#
# 종료하려면 이 터미널에서 Ctrl+C 를 누른다.

set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8770}"

# 최신 상태로 빌드 (index_pdf.html 이 없거나 템플릿이 더 최신이면)
if [ ! -f index_pdf.html ] || [ src/index_pdf.template.html -nt index_pdf.html ]; then
  echo "index_pdf.html 을 빌드합니다…"
  ./build.sh
fi

# 이미 실행 중이면 중복 실행하지 않는다
if curl -s -m 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "프록시가 이미 ${PORT} 포트에서 실행 중입니다."
else
  echo "NVIDIA 프록시를 시작합니다 (포트 ${PORT})…"
  python3 nvidia_proxy.py --port "$PORT" &
  PROXY_PID=$!
  trap 'kill $PROXY_PID 2>/dev/null || true' EXIT INT TERM
  for _ in $(seq 1 20); do
    curl -s -m 1 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1 && break
    sleep 0.3
  done
fi

echo "브라우저에서 요약기를 엽니다…"
open "index_pdf.html"

echo ""
echo "준비되었습니다. 이 터미널을 켜 둔 채로 사용하세요."
echo "종료하려면 Ctrl+C 를 누르세요."
wait
