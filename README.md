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
├── index.html                    # GitHub Pages 루트 → shopping-list/ 로 보내는 리다이렉트
├── .nojekyll                     # GitHub Pages의 Jekyll 처리 비활성화
└── shopping-list/
    └── index.html                # 쇼핑 리스트 앱 (별도 프로젝트, 단일 파일)
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

브라우저에서 바로 사용할 수 있는 간단한 쇼핑 리스트 웹 앱입니다. 의존성 없는 단일 HTML 파일이며, 한글 입력 중 Enter 키가 중복 처리되지 않도록 IME 입력을 고려했습니다.

### 주요 기능

- 쇼핑 아이템 추가
- 아이템 삭제
- 체크박스로 구매 완료 표시
- 완료 항목 일괄 삭제
- 태그 입력창 또는 `#태그`로 분류, 칩으로 확인하고 `×`로 바로 제거
- 태그별 색 구분 (이름 기준이라 어디서나 같은 색)
- 태그별 필터링 (전체 보기 포함)
- 전체/완료 아이템 수 표시
- LocalStorage에 데이터 유지 (기본 동작, 네트워크 불필요)
- JSON 파일로 내보내기 / 가져오기 (오프라인에서도 동작)
- 백업 코드로 기기 간 이동 — 24시간 유효, 한 번 가져가면 소멸
- 한글 IME 입력 호환 (macOS·Windows 모두 Enter 한 번에 추가)
- 다크/라이트 테마, 키보드 접근성, 모바일 대응 단일 페이지 UI

### 실행 방법

온라인에서 바로 쓸 수 있습니다 — **<https://perust.github.io/shopping-listapp/>**

내려받아서 쓰려면 정적 HTML 앱이므로 브라우저에서 직접 열면 됩니다.

```bash
open shopping-list/index.html
```

또는 로컬 서버로 실행합니다.

```bash
python3 -m http.server 8000
```

브라우저에서 `http://localhost:8000/shopping-list/`에 접속합니다.

### 기술 스택

- HTML
- CSS
- Vanilla JavaScript (외부 스크립트·빌드 도구 없음)
- LocalStorage API
- Supabase Postgres — RPC 함수 3개만 사용

### 데이터 저장

**목록은 항상 이 브라우저의 LocalStorage에만 저장됩니다.** 추가·삭제·체크는 전부 로컬에서 즉시 처리되므로 오프라인에서도 그대로 동작하고, 앱을 여는 동안 네트워크 요청이 한 건도 발생하지 않습니다.

우측 상단의 `로컬 저장중` 라벨이 저장 위치를 상시로 알려 줍니다. 제목 아래 줄은 내보내기·가져오기 결과 같은 일시적인 안내에만 씁니다.

### 태그와 필터

태그를 다는 방법이 두 가지입니다. 어느 쪽이든 아이템 입력창 아래 **칩**으로 쌓이고, `추가`를 누르면 그 아이템에 함께 붙습니다.

- **태그 입력창** — 아이템 입력창 아래 작은 칸에 치고 **스페이스나 Enter**를 누르면 칩이 됩니다. 한 번에 여러 개(`유제품 냉장 `)도 됩니다.
- **아이템 입력창에서 `#`** — `우유 2L #유제품 `처럼 `#태그` 뒤에 스페이스를 치면 그 자리에서 칩으로 빠져나갑니다. 스페이스 없이 `#유제품`으로 끝내고 `추가`를 눌러도 태그로 잡힙니다.

칩의 `×`를 누르면 붙기 전에 뺄 수 있고, 태그 입력창이 비어 있을 때 지우기(Backspace)를 누르면 마지막 칩부터 없어집니다. 이름 없이 `추가`를 누르면 칩은 그대로 두고 이름을 입력하라고 알려 줍니다.

스페이스 처리는 keydown이 아니라 **입력값이 들어온 뒤**에 합니다. 한글 조합 중에는 스페이스가 조합을 확정하는 데 먼저 쓰이기 때문입니다.

태그를 쓰기 시작하면 목록 위에 필터 줄이 생깁니다. `전체`와 각 태그가 개수와 함께 나오고, 눌러서 걸러 볼 수 있습니다. 아이템에 붙은 태그 칩을 눌러도 그 태그로 필터링됩니다.

- **필터가 켜져 있을 때** 통계와 `완료 N개 삭제`는 **보이는 항목만** 대상으로 합니다. 안 보이는 항목이 조용히 지워지지 않습니다.
- 필터를 걸어 둔 채 다른 태그의 아이템을 추가하면, 방금 넣은 게 보이도록 `전체`로 되돌아갑니다.
- 어떤 태그의 마지막 아이템이 사라지면 그 태그도 목록에서 빠지고 필터는 `전체`로 돌아갑니다.
- 태그를 하나도 쓰지 않으면 필터 줄은 아예 표시되지 않습니다.

태그는 20자까지이며 중복은 자동으로 정리됩니다. 내보내기·가져오기에도 함께 실려 가고, 태그가 없던 시절에 내보낸 파일도 그대로 읽힙니다.

### 태그 색

색은 **태그 이름을 해시해서** 정합니다. 순서가 아니라 이름으로 정하므로 같은 태그는 목록에서든 필터에서든 다른 기기에서든 늘 같은 색입니다.

색은 네 가지뿐이고 그 이상은 재사용합니다. 서로 구분되는 색이 생각보다 빨리 바닥나기 때문입니다. 임의의 두 태그가 나란히 놓이는 조건(all-pairs)에서 검증해 보면 다섯 색부터는 색각 이상 기준도, 정상 시야 기준(OKLab ΔE 15)도 통과하지 못합니다. 실제로 여덟 색을 넣으면 빨강↔주황이 ΔE 7.1로 **정상 시야로도 구별이 어렵습니다.**

태그는 이름이 항상 함께 보이므로 색은 훑어보기용 보조 신호입니다. 그래서 검증을 통과한 네 색만 쓰고, 그 이상은 색이 겹쳐도 이름으로 구분됩니다. 밝은 테마와 어두운 테마는 각각 그 배경에 맞춰 따로 고른 값이며 자동 반전이 아닙니다.

해시에는 마지막 섞기(mixing) 단계가 들어 있습니다. 없으면 코드포인트가 몰려 있는 한글 태그가 한 색으로 쏠립니다 — 실제로 태그 20개 중 16개가 같은 색이 되었습니다.

### 내보내기 / 가져오기

맨 아래 `내보내기` / `가져오기`를 누르면 **파일**과 **클라우드** 중에서 고릅니다.

**파일** — JSON 파일로 저장하고 다시 불러옵니다. 계정도 네트워크도 필요 없습니다.

| | 동작 |
|---|---|
| 내보내기 → 파일로 | 지금 목록을 `shopping-list-YYYY-MM-DD.json`으로 저장 |
| 가져오기 → 파일에서 | 그 파일을 골라 이 브라우저의 목록을 **통째로 교체** |

**클라우드** — 저장소가 아니라 **1회성 전송함**입니다.

| | 동작 |
|---|---|
| 내보내기 → 클라우드로 | 목록을 올리고 `XXXX-XXXX-XXXX` 형식의 **백업 코드**를 발급 |
| 가져오기 → 클라우드에서 | 그 코드를 붙여넣어 목록을 받고, **서버에서는 즉시 삭제** |

내보낸 뒤에는 화면에 `클라우드 내보내기 상태입니다 · 23시간 47분 남음`과 코드가 계속 떠 있고, `코드 복사` 버튼으로 다시 복사할 수 있습니다. 다음 두 경우에 코드가 사라집니다.

- 누군가 그 코드로 **가져간 순간** — 한 번만 쓸 수 있습니다
- **24시간이 지난 뒤** — 서버에서도 함께 삭제됩니다

이미 쓴 코드나 만료된 코드를 넣으면 목록을 건드리지 않고 안내만 띄웁니다. 내보낸 기기에서 페이지를 열면 그 코드가 아직 유효한지 한 번 확인해서, 이미 소진됐으면 화면 표시를 정리합니다.

가져오기는 모두 덮어쓰기이므로 버튼 자리에서 한 번 더 확인을 받습니다. 진행 상황과 결과는 제목 아래에 표시되고, 실패하면 같은 자리에 빨간 글씨로 알려 줍니다.

### 접근 통제

**코드 자체가 열쇠입니다.** 로그인이 없는 대신, 코드를 모르면 아무것도 할 수 없게 만들었습니다.

소스에 들어 있는 키는 **publishable 키**로, 브라우저 노출을 전제로 만들어진 공개용 키입니다.

- `transfers` 테이블은 `anon` 권한을 전부 회수해 두어 **직접 조회가 `401`** 입니다. 즉 남의 코드 목록을 훑어볼 수 없습니다.
- 접근은 코드를 인자로 받는 함수 세 개(`create_transfer` / `claim_transfer` / `transfer_status`)로만 열려 있습니다.
- 코드는 48비트 난수(12자리 16진수)라 24시간 안에 찍어 맞히기 어렵습니다.

민감한 정보는 넣지 마세요. 코드를 가진 사람은 누구나 그 목록을 받을 수 있습니다.

secret 키는 절대 넣지 마세요. 그 키는 RLS와 권한 설정을 모두 우회합니다.

### Supabase 설정

쓸 프로젝트에 아래 SQL을 실행하고, 파일 상단 `SUPABASE_URL` / `SUPABASE_ANON_KEY`를 바꾸면 됩니다.

```sql
create table public.transfers (
  code text primary key,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default now() + interval '24 hours'
);

create index transfers_expires_at_idx on public.transfers (expires_at);

alter table public.transfers enable row level security;
revoke all on public.transfers from anon, authenticated;

create or replace function public.normalize_transfer_code(p_code text)
returns text language sql immutable as $fn$
  select upper(regexp_replace(coalesce(p_code, ''), '[^0-9A-Za-z]', '', 'g'));
$fn$;

create or replace function public.create_transfer(p_payload jsonb)
returns jsonb language plpgsql security definer set search_path = public as $fn$
declare
  v_code text;
  v_expires timestamptz;
begin
  if p_payload is null or jsonb_typeof(p_payload) <> 'object' then
    raise exception 'invalid payload';
  end if;
  if length(p_payload::text) > 200000 then
    raise exception 'payload too large';
  end if;

  delete from public.transfers t where t.expires_at < now();

  loop
    v_code := upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 12));
    exit when not exists (select 1 from public.transfers t where t.code = v_code);
  end loop;

  insert into public.transfers (code, payload) values (v_code, p_payload)
  returning expires_at into v_expires;

  return jsonb_build_object('code', v_code, 'expires_at', v_expires);
end;
$fn$;

create or replace function public.claim_transfer(p_code text)
returns jsonb language plpgsql security definer set search_path = public as $fn$
declare
  v_payload jsonb;
begin
  delete from public.transfers t where t.expires_at < now();

  delete from public.transfers t
   where t.code = public.normalize_transfer_code(p_code)
     and t.expires_at > now()
  returning t.payload into v_payload;

  return v_payload;
end;
$fn$;

create or replace function public.transfer_status(p_code text)
returns timestamptz language sql security definer stable set search_path = public as $fn$
  select t.expires_at from public.transfers t
   where t.code = public.normalize_transfer_code(p_code)
     and t.expires_at > now();
$fn$;

revoke all on function public.create_transfer(jsonb) from public;
revoke all on function public.claim_transfer(text) from public;
revoke all on function public.transfer_status(text) from public;
grant execute on function public.create_transfer(jsonb) to anon;
grant execute on function public.claim_transfer(text) to anon;
grant execute on function public.transfer_status(text) to anon;
```

만료된 행은 `create_transfer`와 `claim_transfer`가 호출될 때마다 함께 지우므로 별도 스케줄러가 필요 없습니다.
