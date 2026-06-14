"""
메인 앱 (GUI)

실행하면:
  1) 접근 권한 검사 → 승인 안 된 PC면 머신 ID 를 보여주고 종료.
  2) 작은 창이 뜸. "브라우저 열기"를 눌러 로그인 → Shipment ID 붙여넣고 "다운로드".

** 중요(스레드 규칙) **
  Playwright 의 sync API 는 '한 스레드'에서만 호출해야 한다.
  그래서 브라우저/다운로드 작업은 전부 Worker 스레드 하나가 전담하고,
  GUI(메인 스레드)는 명령만 큐로 보낸다.
"""

import queue
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox

from . import __app_name__
from .access import is_authorized, machine_fingerprint
from .downloader import Session
from .paths import downloads_dir, profile_dir

DOWNLOADS = downloads_dir()    # OS별 실제 다운로드 폴더 (윈도우/맥/리눅스)
PROFILE_DIR = profile_dir()    # 로그인 세션 저장 위치


class Worker(threading.Thread):
    """Playwright 세션을 소유하는 단일 워커 스레드."""

    def __init__(self, log_cb):
        super().__init__(daemon=True)
        self.cmds: queue.Queue = queue.Queue()
        self.log = log_cb
        self.session = None

    def run(self):
        while True:
            cmd, arg = self.cmds.get()

            if cmd == "open":
                try:
                    self.log("브라우저를 여는 중...")
                    self.session = Session(PROFILE_DIR, log=self.log).start()
                    self.log("준비 완료. 로그인되어 있는지 확인 후, ID 입력하고 [다운로드]를 누르세요.")
                except Exception as e:
                    self.log(f"[오류] 브라우저 열기 실패: {e}")

            elif cmd == "download":
                if not self.session:
                    self.log("[안내] 먼저 [브라우저 열기 / 로그인]을 누르세요.")
                    continue
                for sid in arg:
                    sid = sid.strip()
                    if not sid:
                        continue
                    try:
                        self.log(f"[{sid}] 문서 조회 중...")
                        folder, saved = self.session.download_all(sid, DOWNLOADS)
                        if saved:
                            self.log(f"[{sid}] 완료: {len(saved)}개 → {folder}")
                        else:
                            self.log(f"[{sid}] 문서를 못 찾음 (검색 결과 또는 선택자 확인 필요)")
                    except Exception as e:
                        self.log(f"[{sid}] 실패: {e}")
                self.log("— 모든 작업 끝 —")

            elif cmd == "quit":
                if self.session:
                    try:
                        self.session.close()
                    except Exception:
                        pass
                break

    def post(self, cmd, arg=None):
        self.cmds.put((cmd, arg))


class App:
    def __init__(self, root):
        self.root = root
        root.title(__app_name__)
        root.geometry("560x470")

        tk.Label(root, text="Shipment ID (한 줄에 하나씩)").pack(anchor="w", padx=10, pady=(10, 0))
        self.ids = scrolledtext.ScrolledText(root, height=6)
        self.ids.pack(fill="x", padx=10)

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
        self.worker.post("download", ids)

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
