"""더블클릭/PyInstaller 용 실행 진입점.

    python run.py
또는 패키지 형태로:
    python -m tkf_downloader
"""

from tkf_downloader.app import main

if __name__ == "__main__":
    main()
