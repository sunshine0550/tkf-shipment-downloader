# TKF Shipment Downloader

Shipment ID 를 여러 개 입력하면, 지정한 **검색 기간** 안의 건들을 찾아
각 건의 문서를 `다운로드/<shipment id>/` 폴더에 자동 저장하는 도구 (TKF 사내용).

동작 원리 (순수 API 방식 — 크롤링/클릭 없음):
1. **로그인이 필요할 때만** 브라우저가 떠서 로그인(MS+MFA)하고, 세션 쿠키
   (`ASP.NET_SessionId`)를 파일(`~/.tkf_session`)에 저장한 뒤 닫힌다. 평소 작업은
   저장된 쿠키로 **순수 HTTP**(브라우저 없음). 쿠키가 만료되면 다시 로그인만 누르면 된다.
   (MS 로그인+MFA 자체는 자동화 불가/금지 — 사람이 통과한 쿠키만 재사용)
2. 로그인 쿠키로 **검색 API** `POST /xCarrier/ECS/GetShipmentHistory` 를 호출(기간 전달) →
   기간 내 목록을 받아 입력한 `DELIVERY_NUM` 의 `SHIPPING_NUM`/`PLANT_ID` 를 찾는다.
3. **상세 API** `GET /xCarrier/ECS/GetShipmentHistoryInfo?deliveryno=..&Shippingno=..&PlantID=..`
   를 호출 → `listShipmentDocumentUrls` 의 파일 URL 들을 받는다.
4. 그 URL 들을 **로그인된 세션 쿠키**로 직접 내려받아 저장한다.
   (`localhost:2028` 프린트 에이전트는 전혀 사용하지 않음)

> 클릭/대기/타임아웃이 없어 빠르다. 검색은 배치당 한 번만 하고, 입력한 ID 들을 그 결과에서 찾는다.

주요 기능:
- **여러 ID 한 번에** — 한 줄에 하나씩 붙여넣으면 각 ID 별 폴더로 분류 저장.
- **검색 기간(전체 공통)** — From/To 한 쌍으로 모든 ID 에 적용. 기본값은 **어제 ~ 오늘**.
- **기간 밖 ID 자동 건너뜀** — 지정 기간에 없는 건은 에러 대신 `⏭ 건너뜀` 으로 표시.
- **실패 문서 알림** — 어떤 문서가 왜(예: HTTP 403) 실패했는지 ID 별로 보여줌.
- **결과 요약** — 끝에 `처리 N / 건너뜀 N / 실패 N`.

## 크로스플랫폼 (맥 · 윈도우)

**맥과 윈도우 모두에서 동일하게 동작한다.** (리눅스도 지원)

- 다운로드한 파일은 각 OS 의 **실제 '다운로드' 폴더** 아래
  `다운로드/<shipment id>/` 에 저장된다 (`tkf_downloader/paths.py` 가 해석):
  - **윈도우**: 레지스트리에서 실제 Downloads 경로를 읽음(사용자가 폴더를 옮겼어도 정확).
    못 읽으면 `%USERPROFILE%\Downloads` 로 떨어짐.
  - **맥**: `~/Downloads`
  - **리눅스**: XDG `user-dirs.dirs` → 없으면 `~/Downloads`
  - **판별 불가 OS**: **윈도우 기준(`홈\Downloads`)** 을 기본값으로 사용.
- 머신 ID(`access.py`)도 OS별로 분기: 윈도우는 레지스트리 `MachineGuid`,
  맥/그 외는 네트워크 어댑터 기반 fallback.
- 로그인 세션은 OS 무관하게 홈 디렉터리의 `~/.tkf_dl_profile` 에 저장.

> ⚠️ 빌드(exe)만은 OS 종속이다. **윈도우용 exe 는 윈도우에서, 맥 앱은 맥에서** 빌드해야 한다
> (아래 6번 참고). 소스 코드(`python run.py`) 자체는 어디서든 그대로 돈다.

## 프로젝트 구조

```
tkf-shipment-downloader/
├─ tkf_downloader/
│  ├─ __init__.py        # 패키지 메타(이름/버전)
│  ├─ __main__.py        # python -m tkf_downloader 진입점
│  ├─ app.py             # GUI + 작업 흐름 (tkinter). 로직 시작점 main()
│  ├─ api.py             # 순수 HTTP API 클라이언트 (검색/상세/다운로드, 브라우저 없음)
│  ├─ auth.py            # 세션 쿠키 캐시 + 로그인 시에만 브라우저 캡처
│  ├─ access.py          # 접근 제어(머신 ID ↔ allowlist, certifi 로 HTTPS 검증)
│  ├─ paths.py           # OS별 다운로드 폴더/프로필/쿠키 경로 해석
│  └─ dates.py           # 검색 기간 기본값(어제~오늘)·형식 변환
├─ run.py                # 실행 진입점(스위치) → app.main() 을 호출
├─ tests/                # pytest 테스트
│  ├─ test_access.py     # 접근 제어(머신 ID/allowlist)
│  ├─ test_api.py        # 검색/상세/다운로드·파일명 정제·세션만료 판정
│  ├─ test_dates.py      # 검색 기간 기본값/형식 변환
│  └─ test_paths.py      # OS별 다운로드 폴더/쿠키 경로 해석
├─ allowlist.example.json
├─ requirements.txt      # 실행 의존성 (playwright, certifi)
├─ requirements-dev.txt  # 개발/테스트 의존성(pytest 포함)
├─ pytest.ini
├─ conftest.py
├─ .gitignore
├─ LICENSE                # 독점 라이선스 (무단/상업적 사용 금지)
└─ README.md
```

> 실행 파일은 `run.py`, 코드 로직이 시작되는 곳은 `app.py` 의 `main()`.
> `app.py` 는 상대 임포트를 쓰므로 **직접 `python app.py` 로는 실행되지 않는다**
> (반드시 `python run.py` 또는 `python -m tkf_downloader`).

---

## 1. 개발(맥)에서 준비

```bash
cd tkf-shipment-downloader
python -m venv .venv && source .venv/bin/activate   # 가상환경 (반드시 켠 상태로 작업)
pip install -r requirements.txt
playwright install chromium      # codegen/내장 브라우저용 (channel=chrome 쓰면 생략 가능)
```

> ⚠️ `pip install` 과 `python run.py` 는 **항상 같은 venv 안에서** 해야 한다.
> venv 를 안 켜면 시스템 파이썬을 써서 패키지가 따로 놀고, `certifi` 누락 같은 문제가 생긴다.

## 2. API / 계정 설정

`tkf_downloader/api.py` 상단 상수가 검색 API 호출에 쓰인다 (TKF ↔ Lam1730 기준):

- `SEARCH_URL` / `DETAIL_URL` — 두 API 주소
- `SEARCH_PLANT_ID = "Lam1730,"` — 검색 payload 의 plant (다른 계정이면 변경)
- `SEARCH_STATUS_CODE = "SPD"`, `SEARCH_FEEDERSYSTEM = "All"` — 검색 기본 필터

검색 기간(GUI From/To)은 API payload 의 `SHIPHISTORY_FROMDATE`/`SHIPHISTORY_TODATE`
(`MM/DD/YYYY HH:MM:SS`)로 그대로 전달된다. 시작 00:00:00, 종료 23:59:59.

> 로그인 동작은 코드에 넣지 않는다 — 사용자가 브라우저에서 직접 로그인하고 그 세션 쿠키를
> 재사용한다. (MS 로그인+MFA 자동화 금지)
> 검색이 한 번에 가져오는 최대 건수는 `SEARCH_URL` 의 `PageSize`(현재 사실상 무제한)로 정해진다.

## 3. 접근 제어 설정 (allowlist)

승인한 PC(머신 ID)에서만 실행되게 한다. 명단(`allowlist.json`)은 **원격에 호스팅**하고,
exe 는 실행할 때마다 그걸 읽어 확인한다 → **사람을 추가/제거해도 exe 재빌드 불필요.**

1. 공개로 읽히는 곳에 `allowlist.json` 을 올린다 (**GitHub Gist 가 가장 쉬움**, 형식은
   `allowlist.example.json` 참고). 내용 예: `{ "allowed": [] }`
2. 그 **Raw URL** 을 `tkf_downloader/access.py` 의 `ALLOWLIST_URL` 에 넣는다.
   - Gist Raw 주소는 **커밋 해시가 없는** 형태(`.../raw/파일명`)를 써야 수정이 바로 반영된다.
   - 또는 환경변수 `TKF_ALLOWLIST_URL` 로 지정 가능.
   - ⚠️ 이 주소는 **exe 빌드 시점에 구워진다.** 주소를 먼저 넣고 빌드할 것.
3. 사용자가 프로그램을 처음 켜면 "머신 ID"가 뜬다. 그 값을 `allowlist.json` 의
   `"allowed"` 배열에 추가하면 그 PC만 사용 가능. 빼면 즉시 차단(권한 회수).

> allowlist 값은 원본 ID 가 아니라 **해시된 짧은 지문**이라 공개돼도 안전하다.
> 머신 ID만 따로 확인하려면: `python -m tkf_downloader.access`
> HTTPS 인증서 검증은 `certifi` 로 처리하므로 맥/윈도우/exe 어디서나 동작한다.
> 로컬 개발 중 접근 제어를 잠깐 끄려면 `access.py` 의 `FAIL_OPEN = True`
> (네트워크 안 되면 통과). **배포 전 반드시 `False` 로 되돌릴 것.**

## 4. 로컬 실행

```bash
source .venv/bin/activate      # venv 켜기
python run.py
# 또는
python -m tkf_downloader
```

흐름: **[브라우저 열기 / 로그인]** → (브라우저에서 직접 로그인) →
Shipment ID 여러 줄 입력 → **검색 기간 From/To** (기본 어제~오늘, `MM/DD/YYYY`) →
**[다운로드]**. 진행/건너뜀/실패가 로그창에 표시된다.
로그인 세션은 `~/.tkf_dl_profile` 에 저장되어 **다음 실행 때 재사용**된다(재로그인 최소화).

## 5. 테스트 실행

```bash
pip install -r requirements-dev.txt
pytest
```

브라우저/네트워크 없이 도는 단위 테스트다:
- `access` — allowlist 응답을 모킹해 허용/거부/실패정책 검증
- `api` — `urlopen` 을 가짜로 끼워 검색/상세/다운로드·파일명 중복·실패 보고·
  세션만료(`AuthExpired`) 판정 검증
- `dates` — 기본 기간(어제~오늘)·형식 변환 검증
- `paths` — OS별 다운로드 폴더/쿠키 경로 해석 검증

(`playwright` 미설치 시 다운로더 테스트는 자동 skip)

---

## 6. 윈도우 비개발자용 배포 (exe 만들기)

> ⚠️ **윈도우용 exe 는 반드시 "윈도우 PC"에서 빌드해야 한다.** 맥에서 만든 건 맥 전용.
> (윈도우 없이 빌드하려면 GitHub Actions 자동 빌드를 쓸 수 있다.)

```bat
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --windowed --name TKFDownloader --collect-all playwright --collect-all certifi run.py
```

`dist\TKFDownloader.exe` 가 생긴다.
- `--collect-all playwright` : 브라우저 구동 드라이버까지 exe 에 포함
- `--collect-all certifi` : HTTPS 인증서 묶음 포함 (allowlist 를 https 로 읽을 때 필요)

### 브라우저 의존성 처리 (둘 중 하나 선택)

- **방법 A (권장, 가장 단순):** 사용자 PC에 **Google Chrome 가 깔려 있으면**
  `auth.py` 의 `channel="chrome"` 덕분에 별도 번들이 필요 없다. 그대로 배포.
- **방법 B (Chrome 없는 PC 대비):** `auth.py` 에서 `channel="chrome"` 줄을 지우고
  Playwright 내장 Chromium 을 쓴다. 이 경우 사용자 PC에서 최초 1회
  `playwright install chromium` 이 필요하므로, 같이 줄 설치용 `setup.bat` 을 만들어 둔다:
  ```bat
  pip install playwright
  playwright install chromium
  ```

### 사용자에게 주는 것
- `TKFDownloader.exe`
- (방법 B면) `setup.bat` 과 간단 설명서

사용자는 exe 더블클릭 → 머신 ID 를 관리자에게 전달 → 관리자가 allowlist(Gist) 에 추가 →
다시 실행하면 사용 가능.

---

## 7. 유지보수 시 주의 — 깨지기 쉬운 부분

> 이 앱은 **외부 사이트(myxcarrier.com)의 비공개 API 동작에 의존**한다. 사이트가 응답
> 형식이나 스펙을 바꾸면 아래 지점들이 가장 먼저 깨진다. 문제가 생기면 여기부터 의심할 것.

1. **사이트 API 스펙 (`api.py`)** — 가장 취약.
   - URL: `SEARCH_URL` / `DETAIL_URL` 경로.
   - 응답 키: `DELIVERY_NUM`, `SHIPPING_NUM`, `PLANT_ID`, `listShipmentDocumentUrls`,
     `DOCUMENT_URL`. 이 중 하나라도 사이트에서 이름이 바뀌면 매칭/다운로드가 조용히 실패한다.

2. **세션 만료 감지 (`api.py` 의 `_json()`)** — 이 사이트는 만료 시 401 을 안 주는 경우가
   많아 **3중으로** 판정한다: ① HTTP 401/403, ② 응답이 JSON 이 아님(로그인 HTML 리다이렉트),
   ③ `{"isRedirect": true}` 또는 `{"logoutUrl": ...}`. 사이트가 만료 응답 방식을 바꾸면
   "세션 만료"를 못 잡거나 엉뚱하게 잡는다.

3. **로그인 완료 판정 (`auth.py`)** — 검색 API 로는 로그인 여부를 알 수 없어
   `window.sessionStorage.getItem('USERNAME')` 폴링 + `ASP.NET_SessionId` 쿠키 존재로
   판정한다. SPA 가 이 키 이름이나 저장 방식을 바꾸면 "로그인 감지 실패(시간 초과)"가 난다.

4. **계정/플랜트 고정값 (`api.py` 상단 상수)** — `SEARCH_PLANT_ID = "Lam1730,"`,
   `SEARCH_STATUS_CODE = "SPD"`, `SEARCH_FEEDERSYSTEM = "All"` 은 특정 계정 기준 하드코딩.
   다른 계정/플랜트로 쓰려면 여기만 바꾸면 된다.

5. **Playwright + Chrome 채널 (`auth.py`)** — `channel="chrome"` 이라 사용자 PC에 실제
   Google Chrome 설치가 필요하다. Chrome 없는 PC 대비는 6번의 "방법 B" 참고.

6. **접근 제어 원격 의존 (`access.py`)** — `ALLOWLIST_URL` 이 살아있어야 한다. `FAIL_OPEN
   = False` 라서 네트워크로 allowlist 를 못 읽으면 **전부 차단**된다(Gist 삭제/사설망 차단
   주의). GUI 스레딩과 무관하게, 이 검사는 앱 시작 시 동기로 수행된다.

7. **GUI 스레딩 규칙 (`app.py`)** — 위젯은 **메인 스레드에서만** 만지고, Worker 스레드 →
   GUI 갱신은 반드시 `root.after(...)` 로 넘긴다. 새 기능 추가 시 워커에서 위젯을 직접
   건드리면 크래시/멈춤이 난다.

> 자주 오는 오해: **"다운로드가 안 돼요"** 의 대부분은 버그가 아니라 **검색 기간 밖의 ID**
> (`⏭ 건너뜀`)다. 날짜 범위부터 확인하게 안내할 것.

  ---

  ## 8. 무단 사용 방지 강화 (TODO — 향후 작업)

  > 현재의 `allowlist.json` 방식은 **"보안"이 아니라 "비개발자 통제 편의 기능"** 이다.
  > 유료로 판매하는 단계에서는 아래 방향으로 강화할 계획. (지금은 미적용)

  ### 현재 방식의 한계 (왜 강화가 필요한가)

  접근 검사(`access.py`)가 **사용자 PC 안에서 실행**되므로, 작정한 사람은 우회할 수 있다:

  - 소스/디컴파일한 코드에서 `if not is_authorized():` 검사를 들어내면 그대로 통과.
  - `FAIL_OPEN` 을 `True` 로 바꾸고 네트워크를 막으면 "못 읽었으니 통과".
  - `hosts`/프록시로 allowlist 요청을 가로채 **가짜 `{"allowed":[...]}`** 를 먹임.
  - exe 도 디컴파일 가능 → 난이도만 올라갈 뿐 위 방법이 통한다.

  > 단, 이걸 우회해 앱을 켜도 **실제 데이터는 회사 사이트 로그인(MS+MFA)** 이 있어야
  > 받을 수 있다. 즉 allowlist 는 "실행 자체를 막는 1차 통제"이고, 진짜 데이터 보호벽은
  > 사이트 로그인이다. **"클라이언트에서만 도는 검사는 결국 우회된다"** 가 핵심 전제.

  ### 방법 A — 서버 프록시 (가장 강력, 권장)

  서비스의 진짜 가치인 **API 노하우(`api.py`: 검색/상세 엔드포인트, payload 형식, 문서
  URL 파싱)** 를 사용자 PC에서 떼어내 **내 서버로 옮긴다.**

  ```
  [현재] 클라이언트가 전부 수행
    app.py + api.py + auth.py  (사용자 PC에 노하우까지 전부 노출)

  [개선] 둘로 분리
    클라이언트(배포): app.py(GUI) + auth.py(브라우저 로그인→쿠키) + 서버 호출 코드
    서버(비공개)   : 라이선스 검증 + api.py(검색/파싱 노하우) + myxcarrier 호출
  ```

  - 클라이언트는 **껍데기** → 크랙해도 노하우가 없어 **복제할 게 없다.**
  - 미납 고객은 **서버에서 응답을 끊으면** 작동 불능 → 검사 코드를 지워도 소용없음.
  - AI 로 클라이언트를 분석시켜도 **서버 코드는 손에 없으므로** 재현 불가.

  **쿠키 처리 선택지** (사용자 세션은 민감정보):
  - (A-1) 풀 프록시: 쿠키까지 서버로 → 보호 최강, 다만 고객사가 "세션을 제3자 서버로?"
    거부할 수 있음.
  - (A-2) **절충(현실적)**: 검색/파싱(노하우)만 서버가 하고, 실제 **파일 다운로드는
    클라이언트가 자기 쿠키로 직접** 수행 → 쿠키가 서버를 안 거쳐 신뢰 부담↓, 노하우는
    여전히 가려짐.

  ### 방법 B — 서명된 라이선스 키 (빠른 대안)

  지금 구조를 유지하되 `allowlist.json` 을 **서명 검증 라이선스**로 교체.

  - 회사마다 결제와 1:1 로 묶인 **라이선스 키** 발급.
  - 비대칭키(예: Ed25519): **개인키(서버 보관)로 서명 생성**, **공개키(클라이언트에 박음)로
    검증만**. 사용자는 공개키를 꺼내도 **새 라이선스를 위조 못 한다**(개인키가 없으므로).
    - 원리: 개인키↔공개키는 수학적 짝이고, 그 사이 계산이 **"검증은 쉬움 / 위조는 사실상
      불가능"** 으로 비대칭이다. 공개키는 **서명의 진위(진짜/가짜)만 판정**할 뿐 새 서명을
      만들 수 없다. payload(내용)가 한 글자라도 바뀌면 서명이 안 맞아 **변조도 즉시 감지**된다.
    - ※ 이는 **서명**의 동작이다(개인키로 찍고 공개키로 확인). **암호화**는 방향이 반대
      (공개키로 잠그고 개인키로 풂)이므로 혼동하지 말 것.
  - 라이선스 payload 에 `company`/`expires` 를 넣어 **만료·회수**를 통제. 키에 고객
    식별자를 박아두면 유출 시 **출처 추적**도 가능.

  > ⚠️  방법 B 의 한계: 서명은 **"가짜 키 위조"는 막지만**, 클라이언트의 **검증 코드 자체를
  > 삭제(`if verify(): → if True:`)하는 것은 못 막는다.** 이 한계를 근본적으로 없애는 것은
  > 방법 A 뿐이다. 그래서 보통 방법 B 는 방법 A 또는 난독화(PyArmor 등)와 함께 쓴다.

  
  - **난독화/무결성 검사**(PyArmor 등): 진짜 보안이 아니라 **시간 벌기**. 캐주얼한 크래킹만 차단.
  - **법적 방어 (B2B 라서 유효)**: 코드의 `LICENSE`(독점)에 더해 고객사와 **사용권 계약(EULA)**
    을 맺으면, 무단 복제 시 민·형사 대응 근거가 된다(저작권 침해는 개인·법인 모두 대상 가능).
    라이선스 키에 고객 식별자를 서명으로 박아두면 추적·입증에 도움. (※ 정확한 법적 판단은
    전문가 상담 필요.)
    
  ### 적용 우선순위 (요약)
  
  1. 여력이 되면 → **방법 A (서버 프록시, A-2 절충안)**. 크랙을 구조적으로 무의미하게 만든다.
  2. 빠르게 가려면 → **방법 B(서명 라이선스) + 방법 C(난독화 + 계약서)**.
  3. 한 가지만 고른다면 → **방법 A**. 나머지는 모두 "시간 벌기"에 가깝다.

---

## 라이선스

**독점(Proprietary) 소프트웨어 — © 2026 박수현. All Rights Reserved.**
자세한 내용은 [`LICENSE`](LICENSE) 참고.
- 저작권자의 사전 서면 허가 없이 **사용·복제·수정·배포 금지** (무단 사용 금지)
- **상업적 이용 금지** (판매·재라이선스·유료 서비스 등)
- 허가받은 **사내 업무 용도로만** 사용
