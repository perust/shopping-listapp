# PDF 문서 AI 요약기

PDF를 드래그&드롭하면 AI가 핵심을 한국어로 정리해 주는 단일 파일 웹 앱입니다.
설치·서버·회원가입 없이 `index_pdf.html`을 브라우저에서 열면 바로 동작합니다.

## 특징

- **드래그&드롭 업로드** — 파일을 끌어놓거나 클릭해서 선택
- **완전 로컬 텍스트 추출** — PDF.js로 브라우저 안에서 처리하며, PDF 원본은 외부로 전송되지 않습니다
- **한국어 요약** — 영문 PDF를 넣어도 요약은 한국어로 나옵니다
- **요약 길이 3단계** — 짧게 / 보통 / 자세히
- **긴 문서 자동 분할** — 30,000자를 넘으면 부분 요약 후 통합(map-reduce)
- **NVIDIA 무료 모델 우선** — NVIDIA API를 1순위로 쓰고, 실패하면 OpenRouter로 자동 전환 (12단계 폴백)
- **결과 활용** — 전체 복사, Markdown 저장, 추출 원문 열람
- **다크/라이트 테마**, 키보드 접근성, 반응형 레이아웃

## 실행 방법

### 권장 — NVIDIA 무료 모델 사용

```bash
./start.sh
```

프록시를 켜고 브라우저를 자동으로 엽니다. 터미널을 켜 둔 채로 사용하고, 끝나면 `Ctrl+C`로 종료합니다.

수동으로 하려면:

```bash
python3 nvidia_proxy.py    # 터미널 1: 프록시 실행 (Ctrl+C로 종료)
open index_pdf.html        # 터미널 2 또는 파일 더블클릭
```

### 프록시 없이 — OpenRouter 사용

```bash
open index_pdf.html
```

프록시가 꺼져 있으면 자동으로 OpenRouter로 요약합니다. 설정 패널의 NVIDIA 배지가 상태(`● 연결됨` / `○ 프록시 꺼짐`)를 보여 줍니다.

### 다시 빌드

소스를 수정했거나 `.env`의 키를 바꿨다면:

```bash
./build.sh    # src/index_pdf.template.html + .env → index_pdf.html
```

## 왜 프록시가 필요한가

NVIDIA API(`integrate.api.nvidia.com`)는 **CORS를 허용하지 않습니다.** 브라우저에서 직접 호출하면 요청이 차단됩니다.

```
브라우저에서 직접 호출 → TypeError: Failed to fetch   (프리플라이트에 ACAO 헤더 없음)
```

서버 없이 여는 정적 HTML에서 NVIDIA 모델을 쓰려면 CORS 헤더를 붙여 주는 중계자가 필요하고, `nvidia_proxy.py`가 그 역할을 합니다. 파이썬 표준 라이브러리만 사용하며 `127.0.0.1`에만 바인딩됩니다.

부수 효과로 **NVIDIA API 키가 HTML에 들어가지 않습니다.** 키는 `.env`에만 있고 프록시가 요청 시점에 주입합니다.

## 구조

```
.
├── index_pdf.html                # 최종 산출물 (빌드 결과, .gitignore 대상)
├── nvidia_proxy.py               # NVIDIA API 로컬 프록시 (CORS 중계 + 키 주입)
├── start.sh                      # 프록시 실행 + 브라우저 열기
├── build.sh                      # .env 의 OpenRouter 키를 템플릿에 주입
├── src/
│   └── index_pdf.template.html   # 소스 (API 키는 플레이스홀더)
├── docs/
│   ├── PRD.md                    # 제품 요구사항 및 기능 명세
│   └── QA_REPORT.md              # QA 테스트 결과 및 결함 수정 내역
├── index.html                    # 쇼핑 리스트 앱 (별도 프로젝트)
└── shopping-list/
    └── index.html                # 쇼핑 리스트 앱 사본
```

## 동작 방식

```
파일 드롭 → 검증(확장자·크기·매직넘버) → PDF.js 파싱 → 페이지별 텍스트 추출
  → 스캔본 판정 → 청킹 → AI 요약(단일 또는 map-reduce) → 결과 렌더링
```

텍스트 추출은 브라우저에서, 요약만 OpenRouter API로 처리합니다.
따라서 네트워크로 나가는 것은 **추출된 텍스트뿐**이며 PDF 파일 자체는 전송되지 않습니다.

## 사용 모델

자동 선택 시 **NVIDIA를 먼저** 쓰고, 실패하면 다음 모델·다음 제공자로 넘어갑니다.
아래 응답 시간은 A4 2페이지(2,371자) 기준 실측값입니다.

### NVIDIA API (프록시 경유) — 1순위

| 순위 | 모델 | 응답 시간 |
|---|---|---|
| 1 | `nvidia/nemotron-3-nano-30b-a3b` | 4.3초 |
| 2 | `nvidia/nemotron-3-super-120b-a12b` | 17.9초 |
| 3 | `nvidia/nemotron-3-ultra-550b-a55b` | 11.6초 |
| 4 | `mistralai/mistral-nemotron` | 9.4초 |
| 5 | `google/gemma-4-31b-it` | 6.9초 |
| 6 | `nvidia/nvidia-nemotron-nano-9b-v2` | 12.9초 |

> `meta/llama-3.3-70b-instruct`(180초 타임아웃)와 `nvidia/llama-3.1-nemotron-70b-instruct`(계정 미제공)는
> 실측에서 쓸 수 없어 제외했습니다.

### OpenRouter (직접 호출) — 2순위

NVIDIA Nemotron 계열 `:free` 모델 6종. 프록시 없이 동작하지만 **하루 50회** 제한이 있습니다.

## 제약 사항

- **NVIDIA는 프록시 필요** — CORS 미허용 때문입니다. 프록시가 꺼져 있으면 앱이 상태를 표시하고 OpenRouter로 대체합니다.
- **OpenRouter 하루 50회** — 초과하면 초기화 시각과 함께 NVIDIA 프록시 실행 방법을 안내합니다.
- **OCR 미지원** — 스캔 이미지 PDF는 감지해 안내만 합니다.
- **파일 크기** — 최대 50MB.
- **OpenRouter 키 노출** — `index_pdf.html`에는 OpenRouter 키가 평문으로 들어 있습니다(`.gitignore` 등록됨). **이 파일을 외부에 공유하지 마세요.** 반면 **NVIDIA 키는 이 파일에 들어 있지 않습니다** — 프록시가 `.env`에서 읽어 주입합니다.
- **프록시 접근 범위** — 프록시가 켜져 있는 동안에는 이 컴퓨터의 다른 프로그램도 `127.0.0.1:8770`을 통해 NVIDIA API를 쓸 수 있습니다. 사용이 끝나면 `Ctrl+C`로 종료하세요.

---

## 함께 있는 프로젝트 — 쇼핑 리스트 앱

이 저장소에는 이전 학습 과제인 쇼핑 리스트 앱이 함께 들어 있습니다.

브라우저에서 바로 사용할 수 있는 간단한 쇼핑 리스트 웹 앱입니다. 별도 백엔드 없이 LocalStorage에 데이터를 저장하며, 한글 입력 중 Enter 키가 중복 처리되지 않도록 IME 입력을 고려했습니다.

### 주요 기능

- 쇼핑 아이템 추가
- 아이템 삭제
- 체크박스로 구매 완료 표시
- 전체/완료 아이템 수 표시
- LocalStorage 기반 데이터 유지
- 한글 IME 입력 호환
- 모바일에서도 보기 쉬운 단일 페이지 UI

### 실행 방법

정적 HTML 앱이므로 브라우저에서 `index.html`을 직접 열면 됩니다.

```bash
git clone https://github.com/perust/shopping-listapp.git
cd shopping-listapp
open index.html
```

또는 로컬 서버로 실행합니다.

```bash
python -m http.server 8000
```

브라우저에서 `http://localhost:8000`에 접속합니다.

### 기술 스택

- HTML
- CSS
- Vanilla JavaScript
- LocalStorage API

### 데이터 저장

목록 데이터는 사용자의 브라우저 LocalStorage에 저장됩니다. 같은 브라우저/도메인에서 다시 열면 이전 목록이 유지됩니다.
