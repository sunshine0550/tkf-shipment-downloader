# TKF Shipment Downloader

Shipment ID 를 입력하면 해당 건의 Forms & Labels 문서들을
`다운로드/<shipment id>/` 폴더에 자동 저장하는 도구 (TKF 사내용).

동작 원리: 페이지가 스스로 호출하는 `GetShipmentHistoryInfo` 응답을 가로채
`listShipmentDocumentUrls` 의 파일 URL 들을 받아, 로그인된 세션 쿠키로 직접 내려받는다.
(`localhost:2028` 프린트 에이전트는 전혀 사용하지 않음)

## 크로스플랫폼 (맥 · 윈도우)

**맥과 윈도우 모두에서 동일하게 동작한다.** (리눅스도 지원)

- 다운로드한 파일은 각 OS 의 **실제 '다운로드' 폴더** 아래
  `다운로드/<shipment id>/` 에 저장된다 (`tkf_downloader/paths.py` 가 해석):
  - **윈도우**: 레지스트리에서 실제 Downloads 경로를 읽음(사용자가 폴더를 옮겼어도 정확).
    못 읽으면 `%USERPROFILE%\Downloads` 로 떨어짐.
  - **맥**: `~/Downloads`
  - **리눅스**: XDG `user-dirs.dirs` → 없으면 `~/Downloads`
  - **판별 불가 OS**: 요청대로 **윈도우 기준(`홈\Downloads`)** 을 기본값으로 사용.
- 머신 ID(`access.py`)도 OS별로 분기: 윈도우는 레지스트리 `MachineGuid`,
  맥/그 외는 네트워크 어댑터 기반 fallback.
- 로그인 세션은 OS 무관하게 홈 디렉터리의 `~/.tkf_dl_profile` 에 저장.

> ⚠️ 빌드(exe)만은 OS 종속이다. **윈도우용 exe 는 윈도우에서, 맥 앱은 맥에서** 빌드해야 한다
> (아래 5번 참고). 소스 코드(`python run.py`) 자체는 어디서든 그대로 돈다.

## 프로젝트 구조

```
tkf-shipment-downloader/
├─ tkf_downloader/
│  ├─ __init__.py        # 패키지 메타(이름/버전)
│  ├─ __main__.py        # python -m tkf_downloader 진입점
│  ├─ app.py             # GUI + 작업 흐름 (tkinter)
│  ├─ downloader.py      # Playwright 인터셉트 & 다운로드 (★선택자 채우는 곳)
│  ├─ access.py          # 접근 제어(머신 ID ↔ allowlist)
│  └─ paths.py           # OS별 다운로드 폴더/프로필 경로 해석
├─ run.py                # 더블클릭/PyInstaller 용 실행 진입점
├─ tests/                # pytest 테스트
│  ├─ test_access.py     # 접근 제어(머신 ID/allowlist) 테스트
│  └─ test_downloader.py # 파일명 정제·다운로드 저장 로직 테스트
├─ allowlist.example.json
├─ requirements.txt      # 실행 의존성
├─ requirements-dev.txt  # 개발/테스트 의존성(pytest 포함)
├─ pytest.ini
├─ conftest.py
├─ .gitignore
└─ README.md
```

---

## 1. 개발(맥)에서 준비

```bash
cd tkf-shipment-downloader
python -m venv .venv && source .venv/bin/activate   # (선택) 가상환경
pip install -r requirements.txt
playwright install chromium      # codegen/내장 브라우저용
```

## 2. ★ 반드시 해야 할 작업: 검색 선택자 채우기

`tkf_downloader/downloader.py` 의 `fetch_document_urls()` 안에
`SELECTOR_검색입력창`, `SELECTOR_검색버튼`, 결과 행 클릭 — 이 3곳을
실제 사이트에 맞게 바꿔야 한다.

가장 쉬운 방법은 **codegen 녹화**:

```bash
playwright codegen https://lamresearch.myxcarrier.com/xCarrier/Home/Index#/ECS/
```

창이 뜨면 로그인 → 검색창에 shipment id 입력 → 검색 → 결과 행 클릭 까지
손으로 해본다. 그러면 그 동작에 해당하는 정확한 선택자 코드가 자동으로 생성된다.
그 코드를 `downloader.py` 의 해당 위치에 붙여넣으면 끝.

> 참고: 결과 행 클릭 대신 "reference# 클릭" 흐름이 맞다면 그 클릭을 녹화하면 된다.
> 핵심은 "상세가 열려서 `GetShipmentHistoryInfo` 가 호출되게" 만드는 것.

## 3. 접근 제어 설정

1. `allowlist.example.json` 을 참고해 `allowlist.json` 을 만든다.
2. 어디든 공개 GET 으로 읽히는 곳에 올린다 (GitHub raw 가 가장 쉬움).
3. `tkf_downloader/access.py` 의 `ALLOWLIST_URL` 을 그 주소로 바꾼다.
   - 또는 환경변수 `TKF_ALLOWLIST_URL` 로 주소를 지정할 수 있다.
4. 사용자가 프로그램을 처음 켜면 "머신 ID"가 뜬다. 그 값을 받아
   `allowlist.json` 의 `"allowed"` 배열에 추가하면 그 PC만 사용 가능.
   - 빼면 즉시 차단됨(권한 회수).

> 머신 ID만 따로 확인하려면: `python -m tkf_downloader.access`

## 4. 로컬 실행/테스트

```bash
python run.py
# 또는
python -m tkf_downloader
```

처음엔 [브라우저 열기 / 로그인] → 로그인 → ID 입력 → [다운로드].
로그인 세션은 `~/.tkf_dl_profile` 에 저장되어 다음 실행 때 재사용된다.

## 4-1. 테스트 실행

```bash
pip install -r requirements-dev.txt
pytest
```

브라우저나 네트워크 없이 도는 단위 테스트다. 접근 제어(`is_authorized`)는
allowlist 응답을 모킹하고, 다운로드는 `ctx.request.get` 을 가짜로 끼워
파일 저장·파일명 중복 처리·실패 응답 skip 등을 검증한다.
(`playwright` 미설치 시 다운로더 테스트는 자동 skip)

---

## 5. 윈도우 비개발자용 배포 (exe 만들기)

> ⚠️ **윈도우용 exe 는 반드시 "윈도우 PC"에서 빌드해야 한다.** 맥에서 만든 건 맥 전용.
> 윈도우 한 대(또는 가상머신)에 Python 을 설치하고 아래를 실행하세요.

```bat
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --windowed --name TKFDownloader run.py
```

`dist\TKFDownloader.exe` 가 생긴다.

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

사용자는 exe 더블클릭 → 머신 ID 를 관리자에게 전달 → 관리자가 allowlist 에 추가 →
다시 실행하면 사용 가능.
