# QA 테스트 보고서 — PDF 문서 AI 요약기

| 항목 | 내용 |
|---|---|
| 테스트 일자 | 2026-08-11 |
| 대상 | `index_pdf.html` (단일 파일) |
| 환경 | macOS 24.6.0 / Google Chrome / 로컬 HTTP + `file://` |
| 방법 | 실제 Chrome 자동화(드래그&드롭 이벤트 실제 발생) + 헤드리스 `file://` 프로브 |
| 결과 | 수용 기준 12/12 통과, 결함 6건 발견 및 전량 수정 |

> **2차 라운드 (NVIDIA 전환)** — 요약 제공자를 NVIDIA API 우선으로 전환하면서 §6에 3건을 추가로 발견·수정했다.

---

## 1. 테스트 픽스처

실제 PDF를 생성해 사용했다 (Chrome 헤드리스 인쇄, fpdf2, Pillow).

| 파일 | 내용 | 검증 목적 |
|---|---|---|
| `ko_article.pdf` | 한글 연구보고서 2페이지 / 2,371자 | 정상 경로, 한국어 요약 |
| `en_paper.pdf` | 영문 논문 2페이지 / 2,677자 | 영문 → 한국어 요약 |
| `long_report.pdf` | 한글 계획서 37페이지 / 33,624자 | 청킹(map-reduce) 경로 |
| `scanned.pdf` | 텍스트 레이어 없는 이미지 PDF | 스캔본 감지 |
| `encrypted.pdf` | 사용자 비밀번호 설정 | 암호화 PDF 처리 |
| `broken.pdf` | `%PDF-` 헤더 + 난수 4KB | 손상 PDF 처리 |
| `fake.pdf` | 확장자만 PDF인 텍스트 | 매직넘버 검증 |
| `notes.txt` | 일반 텍스트 | 형식 검증 |
| `empty.pdf` | 0바이트 | 빈 파일 검증 |

## 2. 발견된 결함과 수정

### 결함 1 (P0) — 백그라운드 탭에서 텍스트 추출이 영구 정지

**증상.** 텍스트 추출이 100%에 도달한 뒤 다음 단계로 넘어가지 않고 무한 대기. 오류도 나지 않고 복구 수단도 없어 새로고침 외에는 방법이 없음.

**원인.** UI 양보를 위해 `requestAnimationFrame`을 사용했는데, 브라우저는 탭이 보이지 않을 때 rAF를 발화시키지 않는다. 진단 결과 `document.visibilityState === "hidden"`, `rafFired === false`.

```
{ hasFocus: true, hidden: true, rafFired: false, visibility: "hidden" }
```

**영향.** 사용자가 처리 중 다른 탭으로 전환하거나 창을 최소화하면 앱이 멈춘다. 긴 문서일수록 다른 일을 하며 기다릴 가능성이 높아 실제 발생 확률이 높다.

**수정.** 화면 표시 여부와 무관하게 동작하는 `MessageChannel` 매크로태스크로 교체했다. `setTimeout`은 백그라운드 탭에서 최소 1초로 제한되므로 선택하지 않았다.

```js
const yieldToUI = (typeof MessageChannel !== "undefined")
  ? () => new Promise(res => {
      const ch = new MessageChannel();
      ch.port1.onmessage = () => { ch.port1.close(); res(); };
      ch.port2.postMessage(0);
    })
  : () => new Promise(res => setTimeout(res, 0));
```

### 결함 2 (P1) — 잘린 JSON 응답이 원시 텍스트로 노출

**증상.** 37페이지 문서를 "자세히"로 요약하면 결과 카드에 `{"title": "디지털 전환 계획…` 같은 원시 JSON이 그대로 표시됨.

**원인.** 모델 응답이 `max_tokens`에 걸려 중간에 끊기면 닫히지 않은 문자열·괄호가 남아 `JSON.parse`가 실패하고, 폴백 경로가 응답 전문을 상세 요약으로 표시했다.

**수정.** 세 겹으로 보강했다.

1. `max_tokens` 상향 (짧게 2,000 / 보통 3,600 / 자세히 6,500)
2. `repairTruncatedJson()` — 문자열·괄호 상태를 추적해 열린 문자열을 닫고 괄호를 역순으로 닫는다. 실패하면 마지막 콤마 뒤의 불완전한 요소를 잘라내며 최대 14회 재시도
3. `extractFieldsByRegex()` — 그래도 실패하면 정규식으로 필드만 건져낸다

**검증.** 12개 케이스 단위 테스트 전부 통과.

| 케이스 | 수정 전 | 수정 후 |
|---|---|---|
| 정상 JSON / 코드펜스 / 서두 텍스트 / 후행 콤마 / `<think>` 태그 / 이스케이프 따옴표 | 통과 | 통과 |
| 문자열 중간 잘림 | **실패** | 통과 |
| 배열 중간 잘림 | **실패** | 통과 |
| 콤마 직후 잘림 | **실패** | 통과 |
| 키 중간 잘림 | **실패** | 통과 |
| 상세요약 중간 잘림 | **실패** | 통과 |
| JSON이 아닌 평문 | 통과(degraded) | 통과(degraded) |

### 결함 3 (P2) — 일일 한도 소진 시 무의미한 모델 순회

**증상.** OpenRouter 계정의 일일 무료 한도가 소진되자 7개 모델을 전부 순회하며 각각 재시도까지 수행했다. 약 10초를 낭비하고, 최종 메시지는 "무료 모델이 혼잡합니다"로 원인을 잘못 안내했다.

**원인.** HTTP 429를 모델 단위 혼잡으로만 분류했다. 실제 응답은 계정 단위 제한이었다.

```
{"error":{"message":"Rate limit exceeded: free-models-per-day", "code":429,
  "metadata":{"headers":{"X-RateLimit-Limit":"50","X-RateLimit-Remaining":"0",
  "X-RateLimit-Reset":"1786406400000"},"limit_source":"openrouter_free_tier_daily"}}}
```

**수정.** 429 본문에서 `free-models-per-day` / `free_tier_daily`를 식별해 `quota` 종류로 분리하고, 모델 전환 없이 즉시 중단하도록 했다. 응답의 `X-RateLimit-Reset`을 파싱해 초기화 시각을 한국 시간으로 안내하고, 개인 키 입력 경로를 제시한다.

수정 후 동작 — 요청 1회로 종료:

> **오늘의 무료 사용 한도를 모두 사용했습니다**
> 오늘 사용할 수 있는 무료 모델 요청 횟수를 모두 사용했습니다. 한도는 2026. 8. 11. 오전 9:00:00에 초기화됩니다.
> 한도가 초기화될 때까지 기다리거나, **설정**에서 본인의 OpenRouter API 키를 입력하면 바로 계속 사용할 수 있습니다.
> `[설정 열기] [다시 시도]`

### 부수 개선

- **클립보드 복사 견고화** — `navigator.clipboard` 실패 시 `execCommand` 폴백이 선택 영역을 복원하도록 고치고, 둘 다 실패하면 Markdown 저장을 안내하는 알림을 표시한다.
- **드롭존 축소** — 파일 선택 후 드롭존을 한 줄로 접어 결과가 화면 위쪽에 오도록 했다.
- **한자 혼용 방지** — 영문 논문 요약에서 "자기注意" 같은 한자 혼용이 관측되어 시스템 프롬프트에 한글 표기 규칙을 추가했다.

## 3. 수용 기준 검증 결과

| ID | 항목 | 결과 | 근거 |
|---|---|---|---|
| AC-1 | 한글 PDF → 한국어 요약 | 통과 | 2페이지/2,371자, 4.2초. 수치 전량 원문 일치 |
| AC-2 | 영문 PDF → 한국어 요약 | 통과 | 3.0초, "짧게"에서 핵심 4개 |
| AC-3 | 대용량 문서 청킹 | 통과 | 37페이지 → 2청크 → 통합, 37.5초, 핵심 10개 |
| AC-4 | 비-PDF 차단 | 통과 | `.txt`/위장 PDF/빈 파일 3종 모두 한국어 안내 |
| AC-5 | 손상 PDF | 통과 | "PDF 파일이 손상되어 열 수 없습니다." |
| AC-6 | 암호화 PDF | 통과 | "비밀번호로 보호된 PDF입니다." |
| AC-7 | 스캔본 | 통과 | 0자 감지 → OCR 미지원 안내 |
| AC-8 | 모델 폴백 | 통과 | 결함 주입으로 7단계 전환 및 안내 로그 확인 |
| AC-9 | 복사·다운로드 | 통과 | `테스트문서_요약.md` 생성 확인, 복사 폴백 보강 |
| AC-10 | 콘솔 오류 없음 | 통과 | 전 테스트 0건 |
| AC-11 | PDF 바이너리 미전송 | 통과 | 파일 225,828바이트, 외부 전송 본문 3,278자, PDF 시그니처 미포함 |
| AC-12 | `file://` 동작 | 통과 | 아래 프로브 결과 |

### `file://` 프로브 결과

Chrome 확장이 `file://`을 열 수 없어 헤드리스 Chrome으로 별도 검사했다.

```json
{
  "protocol": "file:",  "isSecureContext": true,
  "cdnScript": "OK",
  "workerFetch": "OK (1087181 chars)",
  "pdfPages": 1,
  "extractedText": "FILE PROTOCOL EXTRACTION OK 12345",
  "extractionMatches": "OK",
  "workerUsed": "blob worker",
  "openrouterCors": "OK (status 401, body readable: true)",
  "localStorage": "OK"
}
```

## 4. 테스트 중 발생한 환경 이슈 (앱 결함 아님)

- **포트 점유 충돌** — 같은 샌드박스에서 병행 중이던 다른 프로젝트가 04:27에 8765 포트를 가져가, 일부 검증이 다른 앱을 대상으로 실행되었다. 전용 포트(8931)로 이전하고 이후 모든 검증 전에 `<title>`과 신규 함수 존재 여부로 페이지 신원을 확인했다.
- **일일 한도 소진** — QA 과정에서 OpenRouter 무료 50회를 모두 사용했다. 이 덕분에 결함 3을 실제 조건에서 발견하고 수정 후 재현 검증까지 할 수 있었다.

## 5. 2차 라운드 — NVIDIA API 전환 검증

OpenRouter 하루 50회 제한 때문에 NVIDIA API를 1순위 제공자로 전환하고 재검증했다.

### 5.1 사전 실측 — CORS 및 모델

NVIDIA 직접 호출 가능 여부를 두 방법으로 재확인했고, 결과는 동일했다.

| 확인 방법 | 결과 |
|---|---|
| `integrate.api.nvidia.com` 프리플라이트 | HTTP 200, **ACAO 헤더 없음** |
| `ai.api.nvidia.com` 프리플라이트 | HTTP 200, **ACAO 헤더 없음** |
| 브라우저 `fetch` | `TypeError: Failed to fetch` |

따라서 최소 로컬 프록시(`nvidia_proxy.py`, 파이썬 표준 라이브러리만 사용)를 도입했다.

NVIDIA 모델 10종을 실측해 사용 가능한 6종을 선별했다.

| 모델 | 결과 |
|---|---|
| `nvidia/nemotron-3-nano-30b-a3b` | 4.3초, 핵심 5개 — **1순위 채택** |
| `google/gemma-4-31b-it` | 6.9초 |
| `mistralai/mistral-nemotron` | 9.4초 |
| `nvidia/nemotron-3-ultra-550b-a55b` | 11.6초 |
| `nvidia/nvidia-nemotron-nano-9b-v2` | 12.9초 |
| `nvidia/nemotron-3-super-120b-a12b` | 17.9초 |
| `nvidia/llama-3.3-nemotron-super-49b-v1.5` | 41.1초 (느려서 예비) |
| `meta/llama-3.3-70b-instruct` | **180초 타임아웃 — 제외** |
| `nvidia/llama-3.1-nemotron-70b-instruct` | **계정 미제공 — 제외** |
| `nvidia/nemotron-nano-3-30b-a3b` | **404 — 제외** |

### 5.2 결함 4 (P0) — 요약 성공 후 오류 알림 표시

**증상.** NVIDIA로 요약이 정상 완료됐는데도 "요약에 실패했습니다 — source is not defined" 오류가 떴다.

**원인.** 제공자 리팩터링 때 `const { key, source } = getApiKey();`를 제거하면서, `source`를 참조하는 죽은 코드 한 줄이 남았다. `renderResult()` 직후 `ReferenceError`가 발생해 catch 블록이 오류 알림을 띄웠다.

**수정.** 죽은 코드를 제거했다. 요약 성공 후 알림 없이 결과만 표시되는 것을 재확인했다.

### 5.3 결함 5 (P1) — 모델 선택이 조용히 무시됨

**증상.** 사용자가 NVIDIA 모델을 명시적으로 선택했는데 프록시가 꺼져 있으면, 아무 설명 없이 OpenRouter로 요약되고 "OpenRouter 한도 소진" 오류만 나왔다.

**원인.** `refreshProviders()`가 모델 목록을 재구성할 때 NVIDIA 항목을 `disabled` 처리하고, 선택값이 비활성 항목이면 `auto`로 되돌렸다. 사용자의 선택 의도가 소리 없이 사라졌다.

**수정.** NVIDIA 항목을 비활성화하지 않고 선택값을 유지한다. 실행 시점에 프록시 실행 방법을 안내하는 오류를 내는 편이 낫다는 판단이다.

수정 후:

> **NVIDIA 프록시에 연결할 수 없습니다**
> 이 파일이 있는 폴더에서 `python3 nvidia_proxy.py` 를 실행한 뒤 **프록시 다시 확인**을 눌러 주세요.
> `[프록시 다시 확인] [설정 열기] [다시 시도]`

함께, OpenRouter 한도 소진 메시지에도 프록시 실행 안내를 추가했다. 그 상황에서 가장 실행 가능한 해결책이기 때문이다.

### 5.4 결함 6 (P1) — 좁은 화면에서 헤더 붕괴

**증상.** 폭 600px 이하에서 제목이 **글자당 한 줄**로 세로로 늘어지며 화면 전체가 읽을 수 없게 됐다.

**원인.** `@media (max-width:600px)`에서 `.top-actions{width:100%}`를 주었는데 `header.top`에 `flex-wrap`이 없었다. 줄바꿈이 불가능하니 버튼 영역이 505px을 차지하고 제목 영역은 17px로 짓눌렸다.

```
{ innerWidth: 533, headerFlexWrap: "nowrap", actionsWidth: 505, h1Width: 17.1 }
```

1차 라운드에서 1496px 폭으로만 테스트해 놓친 기존 결함이다.

**수정.** `header.top`에 `flex-wrap:wrap`을, 제목 영역에 `.brand{flex:1 1 220px; min-width:0}`을 추가했다.

**검증.** iframe으로 실제 뷰포트 폭을 바꿔 측정했다.

| 폭 | 제목 높이 | 버튼 줄바꿈 | 가로 스크롤 |
|---|---|---|---|
| 360px | 33px (1줄) | 예 | 없음 |
| 420px | 33px (1줄) | 예 | 없음 |
| 533px | 33px (1줄) | 예 | 없음 |
| 768px | 33px (1줄) | 아니오 (데스크톱 배치) | 없음 |

### 5.5 NVIDIA 경로 검증 결과

| 항목 | 결과 |
|---|---|
| 프록시 health / CORS 프리플라이트 | 통과 (`ACAO: *`) |
| 한글 PDF 요약 (2페이지) | 4.2초, 제공자 = NVIDIA, 한자 혼용 0건 |
| 대용량 문서 (37페이지 / 33,624자) | 41.4초, 2청크 분할 → 통합 성공 |
| 프록시 꺼짐 감지 | 배지 `○ 프록시 꺼짐`, 자동 모드가 OpenRouter로 전환 |
| 복구 흐름 (프록시 켜기 → 다시 확인 → 요약) | 통과, 모델 선택 유지 |
| 오류 6종 회귀 | 전부 통과 |
| 콘솔 오류 | 0건 |
| **`file://` → `http://127.0.0.1:8770`** | **통과** — health, POST 프리플라이트, 실제 요약 응답 모두 성공 |

`file://` 프로브 결과:

```json
{
  "protocol": "file:",  "isSecureContext": true,
  "proxyHealth": "OK (ok=true, 모델 7개)",
  "proxyChat": "OK → \"파일 프로토콜 확인\""
}
```

Chrome의 사설 네트워크 접근 제한에 걸리지 않아, `index_pdf.html`을 더블클릭으로 열어도 NVIDIA 모델을 쓸 수 있다.

### 5.6 부수 개선

- **한자 혼용 방지 강화** — NVIDIA nano-30b가 "其中" 같은 한자를 섞어 출력했다. 시스템 프롬프트뿐 아니라 사용자 프롬프트에도 구체적 예시와 함께 규칙을 넣어 해결했다(재검증 시 한자 0건).
- **핵심 포인트 상한** — "자세히"에서 모델이 19개를 반환한 사례가 있어 안전 상한 20개를 두었다.

## 6. 남은 한계

| 항목 | 내용 |
|---|---|
| OCR 미지원 | 스캔 이미지 PDF는 감지 후 안내만 한다 (PRD 비목표 N1) |
| NVIDIA는 프록시 필요 | CORS 미허용 때문. 프록시를 켜지 않으면 OpenRouter로 대체된다 |
| OpenRouter 하루 50회 | 대체 경로의 한도. NVIDIA 경로에는 적용되지 않는다 |
| OpenRouter 키 평문 내장 | 정적 파일 구조상 불가피. `.gitignore`로 제외. **NVIDIA 키는 내장하지 않는다** |
| 프록시 접근 범위 | 실행 중에는 같은 컴퓨터의 다른 프로그램도 `127.0.0.1:8770`을 쓸 수 있다 |
| 요약 품질 편차 | 무료 모델 특성상 드물게 오탈자가 섞인다 (예: "보안 위협 대응" → "보안 협대응") |
