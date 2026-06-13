"""テスト共通設定。"""

import os

# pytest-qt が PySide6 を使用するよう明示
os.environ.setdefault("QT_API", "pyside6")
