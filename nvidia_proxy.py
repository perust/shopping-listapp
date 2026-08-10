#!/usr/bin/env python3
"""
NVIDIA API 로컬 프록시

NVIDIA의 API(integrate.api.nvidia.com)는 CORS를 허용하지 않아 브라우저에서 직접
호출할 수 없다. 이 프록시가 CORS 헤더를 붙여 중계하면 index_pdf.html 이
NVIDIA 무료 모델을 사용할 수 있다.

부수 효과로 API 키가 HTML 파일에 들어가지 않는다. 키는 .env 에만 존재하고
프록시가 요청 시점에 주입한다.

사용법:
    python3 nvidia_proxy.py            # 127.0.0.1:8770 에서 실행
    python3 nvidia_proxy.py --port 9000

종료: Ctrl+C

주의: 프록시가 켜져 있는 동안에는 이 컴퓨터의 다른 프로그램도 127.0.0.1:8770 을
통해 NVIDIA API를 사용할 수 있다. 사용이 끝나면 종료할 것.
"""

import argparse
import json
import os
import pathlib
import ssl
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODELS_URL = "https://integrate.api.nvidia.com/v1/models"
ROOT = pathlib.Path(__file__).resolve().parent
TIMEOUT = 180

# 요약에 사용할 무료 모델 (앞에서부터 시도)
ALLOWED_MODELS = [
    "nvidia/nemotron-3-nano-30b-a3b",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "mistralai/mistral-nemotron",
    "google/gemma-4-31b-it",
    "nvidia/nvidia-nemotron-nano-9b-v2",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
]


def load_api_key():
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if key:
        return key
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "NVIDIA_API_KEY":
                return v.strip().strip('"').strip("'")
    return ""


def make_ssl_context():
    """macOS 파이썬은 기본 CA 번들이 없는 경우가 있어 명시적으로 잡아 준다."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    for p in ("/etc/ssl/cert.pem", "/private/etc/ssl/cert.pem"):
        if os.path.exists(p):
            try:
                return ssl.create_default_context(cafile=p)
            except Exception:
                pass
    return ssl.create_default_context()


API_KEY = load_api_key()
SSL_CTX = make_ssl_context()


class Handler(BaseHTTPRequestHandler):
    server_version = "NvidiaProxy/1.0"

    # ---------- 공통 ----------
    def _cors(self):
        # file:// 에서 열면 Origin 이 null 이므로 * 로 허용한다.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Title")
        self.send_header("Access-Control-Max-Age", "86400")

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status, message, code=None):
        self._send_json(status, {"error": {"message": message, "code": code or status}})

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    # ---------- 라우팅 ----------
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path == "/health":
            self._send_json(200, {
                "ok": bool(API_KEY),
                "provider": "nvidia",
                "models": ALLOWED_MODELS,
                "detail": "준비 완료" if API_KEY else ".env 에 NVIDIA_API_KEY 가 없습니다",
            })
            return

        if path in ("/", "/index_pdf.html"):
            f = ROOT / "index_pdf.html"
            if not f.exists():
                self._send_error(404, "index_pdf.html 을 찾을 수 없습니다.")
                return
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self._cors()
            self.end_headers()
            self.wfile.write(data)
            return

        self._send_error(404, "지원하지 않는 경로입니다: " + path)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/v1/chat/completions", "/chat/completions"):
            self._send_error(404, "지원하지 않는 경로입니다: " + path)
            return

        if not API_KEY:
            self._send_error(401, ".env 에 NVIDIA_API_KEY 가 없습니다. 키를 넣고 프록시를 다시 실행해 주세요.")
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw)
        except Exception as e:
            self._send_error(400, "요청 본문을 해석할 수 없습니다: %s" % e)
            return

        model = payload.get("model", "")
        if model and model not in ALLOWED_MODELS:
            self._send_error(400, "허용되지 않은 모델입니다: %s" % model)
            return

        # OpenRouter 전용 필드는 NVIDIA 가 거부하므로 제거한다.
        payload.pop("reasoning", None)

        sys.stderr.write("→ %s (%d자 요청)\n" % (model or "?", len(raw)))

        req = urllib.request.Request(
            NVIDIA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as r:
                body = r.read()
                status = r.status
        except urllib.error.HTTPError as e:
            body = e.read()
            status = e.code
            sys.stderr.write("← HTTP %d %s\n" % (status, body[:160].decode("utf8", "replace")))
            # NVIDIA 오류 형식을 앱이 아는 형태로 정규화한다.
            try:
                d = json.loads(body)
            except Exception:
                d = {}
            msg = ""
            if isinstance(d, dict):
                err = d.get("error")
                if isinstance(err, dict):
                    msg = err.get("message", "")
                elif isinstance(err, str):
                    msg = err
                msg = msg or d.get("detail") or d.get("message") or ""
            self._send_error(status, msg or ("NVIDIA API 오류 (HTTP %d)" % status), status)
            return
        except urllib.error.URLError as e:
            sys.stderr.write("← 연결 실패: %s\n" % e)
            self._send_error(502, "NVIDIA API에 연결할 수 없습니다: %s" % getattr(e, "reason", e))
            return
        except Exception as e:
            sys.stderr.write("← 오류: %s\n" % e)
            self._send_error(500, "프록시 내부 오류: %s" % e)
            return

        sys.stderr.write("← HTTP %d (%d바이트)\n" % (status, len(body)))
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Proxy-Provider", "nvidia")
        self._cors()
        self.end_headers()
        self.wfile.write(body)


def main():
    ap = argparse.ArgumentParser(description="NVIDIA API 로컬 프록시")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    if not API_KEY:
        print("경고: .env 에서 NVIDIA_API_KEY 를 찾지 못했습니다. 요약 요청이 401로 실패합니다.\n")
    else:
        print("NVIDIA API 키를 불러왔습니다 (%s…%s)\n" % (API_KEY[:6], API_KEY[-4:]))

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print("=" * 58)
    print(" NVIDIA 프록시 실행 중")
    print(" 주소     : http://%s:%d" % (args.host, args.port))
    print(" 앱 열기  : http://%s:%d/  (또는 index_pdf.html 을 직접 열기)" % (args.host, args.port))
    print(" 종료     : Ctrl+C")
    print("=" * 58)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
        srv.shutdown()


if __name__ == "__main__":
    main()
