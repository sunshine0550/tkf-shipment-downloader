"""pytest 가 저장소 루트를 import 경로에 올려 `tkf_downloader` 를 찾게 한다."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
