# frontend/CLAUDE.md — 화면 코드 작업 규칙

저장소 맨 위 `CLAUDE.md`의 규칙을 먼저 따른다. 화면 코드는 아래 문서를 따른다.

- 원칙(폴더 구조, 상태 관리, 이름 규칙, 오류 처리, 토큰): `docs/frontend/principles.md`
- 화면별 명세(상태, 동작, 입력 검증, 수용 기준): `docs/frontend/screens/`
- 디자인 토큰: `src/styles/tokens.css` — 색·간격·글자 크기를 코드에 직접 쓰지 않는다
- 공통 컴포넌트: `src/ui/` (견본은 `npm run dev` 뒤 `/ui`)

빠른 규칙
1. 서버 데이터는 TanStack Query, 화면 안 상태는 useState, 필터·정렬·쪽은 주소에 둔다.
2. 버튼·배지·표·모달·페이지 머리는 `src/ui/`에서 가져온다. 새로 만들지 않는다.
3. 서버 오류는 `ApiError`로 받고 400은 칸 아래, 읽기 실패는 이전 값 흐리게 + 안내 띠로 보인다. alert·confirm은 쓰지 않는다.
4. 화면 명세에 없는 동작은 만들지 않는다. 문서끼리 다르면 묻는다.
5. 확인: `npm run build`(타입 검사 포함)가 통과해야 한다.
