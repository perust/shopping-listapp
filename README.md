# 쇼핑 리스트 앱

브라우저에서 바로 사용할 수 있는 간단한 쇼핑 리스트 웹 앱입니다. 별도 백엔드 없이 LocalStorage에 데이터를 저장하며, 한글 입력 중 Enter 키가 중복 처리되지 않도록 IME 입력을 고려했습니다.

## 주요 기능

- 쇼핑 아이템 추가
- 아이템 삭제
- 체크박스로 구매 완료 표시
- 전체/완료 아이템 수 표시
- LocalStorage 기반 데이터 유지
- 한글 IME 입력 호환
- 모바일에서도 보기 쉬운 단일 페이지 UI

## 프로젝트 구조

```text
.
├── index.html          # 루트 실행 파일
├── shopping-list/
│   └── index.html      # 쇼핑 리스트 앱 사본/하위 실행 파일
└── README.md
```

## 실행 방법

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

## 기술 스택

- HTML
- CSS
- Vanilla JavaScript
- LocalStorage API

## 데이터 저장

목록 데이터는 사용자의 브라우저 LocalStorage에 저장됩니다. 같은 브라우저/도메인에서 다시 열면 이전 목록이 유지됩니다.
