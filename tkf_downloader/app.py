"""
메인 앱 (GUI)

실행하면:
  1) 접근 권한 검사 → 승인 안 된 PC면 머신 ID 를 보여주고 종료.
  2) 작은 창이 뜸. "브라우저 열기"를 눌러 로그인 → Shipment ID 붙여넣고 "다운로드".

** 동작 방식 **
  - 평소 작업(검색·다운로드)은 저장된 세션 쿠키로 '순수 HTTP'(브라우저 없음).
  - 로그인이 필요할 때만 브라우저가 떠서 로그인 → 쿠키를 저장하고 닫힌다.
  - 작업은 Worker 스레드 하나가 전담하고(특히 로그인 시 Playwright), GUI 는 명령만 보낸다.
"""

import queue
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox

from . import __app_name__
from .access import is_authorized, machine_fingerprint
from .api import ApiClient, AuthExpired
from .auth import capture_cookie_via_browser, load_cookie_header
from .paths import downloads_dir
from .dates import default_range_display, to_api_range

DOWNLOADS = downloads_dir()    # OS별 실제 다운로드 폴더 (윈도우/맥/리눅스)


def _enable_ctrl_clipboard(widget):
    """Cmd/Ctrl + C/V/X 를 클립보드에서 직접 처리한다.

    맥 Tk + 한글 입력기에서 기본 ⌘V 가 안 먹는 경우가 있어, 가상 이벤트에 기대지 않고
    직접 넣어준다. 'break' 로 기본 동작을 막아 중복 붙여넣기를 방지한다.
    """
    def paste(_e):
        try:
            text = widget.clipboard_get()
        except tk.TclError:
            return "break"
        try:
            widget.delete("sel.first", "sel.last")   # 선택 영역이 있으면 교체
        except tk.TclError:
            pass
        widget.insert("insert", text)
        return "break"

    def copy(_e):
        try:
            sel = widget.selection_get()
            widget.clipboard_clear()
            widget.clipboard_append(sel)
        except tk.TclError:
            pass
        return "break"

    def cut(_e):
        copy(_e)
        try:
            widget.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        return "break"

    for seq in ("<Control-v>", "<Command-v>"):
        widget.bind(seq, paste)
    for seq in ("<Control-c>", "<Command-c>"):
        widget.bind(seq, copy)
    for seq in ("<Control-x>", "<Command-x>"):
        widget.bind(seq, cut)


class Worker(threading.Thread):
    """로그인(쿠키 캡처)과 API 다운로드를 전담하는 단일 워커 스레드."""

    def __init__(self, log_cb):
        super().__init__(daemon=True)
        self.cmds: queue.Queue = queue.Queue()
        self.log = log_cb
        self.cookie = load_cookie_header()   # 저장된 쿠키가 있으면 바로 사용

    def run(self):
        while True:
            cmd, arg = self.cmds.get()

            if cmd == "open":
                try:
                    self.cookie = capture_cookie_via_browser(self.log)
                    self.log("이제 ID 입력하고 [다운로드]를 누르세요.")
                except Exception as e:
                    self.log(f"[오류] 로그인 실패: {e}")

            elif cmd == "download":
                if not self.cookie:
                    self.cookie = load_cookie_header()
                if not self.cookie:
                    self.log("[안내] 먼저 [브라우저 열기 / 로그인]을 누르세요.")
                    continue
                ids, from_text, to_text = arg
                try:
                    api_from, api_to = to_api_range(from_text, to_text)
                except ValueError:
                    self.log("[오류] 날짜 형식이 잘못됐습니다. MM/DD/YYYY 로 입력하세요 (예: 06/13/2026)")
                    continue

                client = ApiClient(self.cookie, self.log)
                self.log(f"검색 기간: {api_from}  ~  {api_to}")
                self.log("문서 목록 조회 중... (API)")
                try:
                    rows = client.search_shipments(api_from, api_to)
                except AuthExpired:
                    self.log("[안내] 세션이 만료됐어요. [브라우저 열기 / 로그인]을 다시 눌러 로그인하세요.")
                    continue
                except Exception as e:
                    self.log(f"[오류] 검색 실패: {e}")
                    continue

                # DELIVERY_NUM 으로 빠르게 찾도록 색인
                index = {}
                for r in rows:
                    dn = r.get("DELIVERY_NUM") if isinstance(r, dict) else None
                    if dn and dn not in index:
                        index[dn] = r
                self.log(f"기간 내 {len(index)}건 조회됨.")
                if not rows:
                    self.log("  (이 기간에 해당하는 shipment 가 없어요. 날짜 범위를 확인하세요.)")

                done = skipped = errored = 0
                for sid in ids:
                    sid = sid.strip()
                    if not sid:
                        continue
                    row = index.get(sid)
                    if not row:
                        self.log(f"[{sid}] ⏭ 기간 내 목록에 없음 — 건너뜀")
                        skipped += 1
                        continue
                    try:
                        self.log(f"[{sid}] 문서 다운로드 중...")
                        folder, saved, failed = client.download_row(row, DOWNLOADS)
                        if saved or failed:
                            self.log(f"[{sid}] 완료: 성공 {len(saved)}개 / 실패 {len(failed)}개 → {folder}")
                            if failed:
                                self.log(f"[{sid}] ⚠ 실패한 문서 {len(failed)}개:")
                                for desc, reason in failed:
                                    self.log(f"    ✗ {desc} — {reason}")
                        else:
                            self.log(f"[{sid}] 문서 없음")
                        done += 1
                    except AuthExpired:
                        self.log(f"[{sid}] 세션 만료 — [브라우저 열기 / 로그인] 후 다시 시도하세요.")
                        errored += 1
                        break
                    except Exception as e:
                        self.log(f"[{sid}] 실패: {e}")
                        errored += 1
                self.log(f"— 끝 — 처리 {done} / 건너뜀 {skipped} / 실패 {errored}")

            elif cmd == "quit":
                break

    def post(self, cmd, arg=None):
        self.cmds.put((cmd, arg))


class App:
    def __init__(self, root):
        self.root = root
        root.title(__app_name__)
        root.geometry("720x520")

        # 검색 기간 (기본: 어제 ~ 오늘)
        df, dt = default_range_display()
        date_row = tk.Frame(root)
        date_row.pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(date_row, text="검색 기간  From").pack(side="left")
        self.from_date = tk.Entry(date_row, width=12)
        self.from_date.insert(0, df)
        self.from_date.pack(side="left", padx=(4, 8))
        _enable_ctrl_clipboard(self.from_date)
        tk.Label(date_row, text="To").pack(side="left")
        self.to_date = tk.Entry(date_row, width=12)
        self.to_date.insert(0, dt)
        self.to_date.pack(side="left", padx=4)
        _enable_ctrl_clipboard(self.to_date)
        tk.Label(date_row, text="(MM/DD/YYYY)").pack(side="left", padx=4)

        tk.Label(root, text="Shipment ID (한 줄에 하나씩)").pack(anchor="w", padx=10, pady=(10, 0))
        self.ids = scrolledtext.ScrolledText(root, height=6)
        self.ids.pack(fill="x", padx=10)
        _enable_ctrl_clipboard(self.ids)

        btns = tk.Frame(root)
        btns.pack(fill="x", padx=10, pady=8)
        tk.Button(btns, text="1) 브라우저 열기 / 로그인", command=self.open_browser).pack(side="left")
        tk.Button(btns, text="2) 다운로드", command=self.download).pack(side="left", padx=8)

        tk.Label(root, text="진행 로그").pack(anchor="w", padx=10)
        self.logbox = scrolledtext.ScrolledText(root, height=12, state="disabled")
        self.logbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.worker = Worker(self.log_threadsafe)
        self.worker.start()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def log_threadsafe(self, msg):
        # 워커 스레드 → GUI 갱신은 after 로 메인 스레드에서 처리
        self.root.after(0, self._append_log, msg)

    def _append_log(self, msg):
        self.logbox.configure(state="normal")
        self.logbox.insert("end", msg + "\n")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def open_browser(self):
        self.worker.post("open")

    def download(self):
        ids = self.ids.get("1.0", "end").splitlines()
        self.worker.post("download", (ids, self.from_date.get(), self.to_date.get()))

    def on_close(self):
        self.worker.post("quit")
        self.root.destroy()


def main():
    if not is_authorized():
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "접근 거부",
            "이 PC는 사용 승인이 되어 있지 않습니다.\n\n"
            "아래 머신 ID를 관리자에게 보내 승인을 받으세요:\n\n"
            f"{machine_fingerprint()}",
        )
        return

    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
