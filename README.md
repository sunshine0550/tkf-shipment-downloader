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

`tkf_downloader/downloader.py` 상단 상수가 검색 API 호출에 쓰인다 (TKF ↔ Lam1730 기준):

- `SEARCH_URL` / `DETAIL_URL` — 두 API 주소
- `SEARCH_PLANT_ID = "Lam1730,"` — 검색 payload 의 plant (다른 계정이면 변경)
- `SEARCH_STATUS_CODE = "SPD"`, `SEARCH_FEEDERSYSTEM = "All"` — 검색 기본 필터

검색 기간(GUI From/To)은 API payload 의 `SHIPHISTORY_FROMDATE`/`SHIPHISTORY_TODATE`
(`MM/DD/YYYY HH:MM:SS`)로 그대로 전달된다. 시작 00:00:00, 종료 23:59:59.

> 로그인 동작은 코드에 넣지 않는다 — 사용자가 브라우저에서 직접 로그인하고 그 세션 쿠키를
> 재사용한다. (MS 로그인+MFA 자동화 금지)
> 검색이 한 번에 가져오는 최대 건수는 `SEARCH_URL` 의 `PageSize`(기본 2000)로 정해진다.

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
  `downloader.py` 의 `channel="chrome"` 덕분에 별도 번들이 필요 없다. 그대로 배포.
- **방법 B (Chrome 없는 PC 대비):** `downloader.py` 에서 `channel="chrome"` 줄을 지우고
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

## 라이선스

**독점(Proprietary) 소프트웨어 — © 2026 박수현. All Rights Reserved.**
자세한 내용은 [`LICENSE`](LICENSE) 참고.
- 저작권자의 사전 서면 허가 없이 **사용·복제·수정·배포 금지** (무단 사용 금지)
- **상업적 이용 금지** (판매·재라이선스·유료 서비스 등)
- 허가받은 **사내 업무 용도로만** 사용
