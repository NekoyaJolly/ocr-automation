"""OCR Automation アプリケーション共通の例外クラス定義。"""


class OCRAutomationError(Exception):
    """アプリケーション基底例外。"""


class OCRError(OCRAutomationError):
    """OCR 処理に関する例外。"""


class OCREngineInitError(OCRError):
    """OCR エンジンの初期化に失敗した場合の例外。"""


class OCRProcessError(OCRError):
    """OCR 処理（推論）に失敗した場合の例外。"""


class TemplateError(OCRAutomationError):
    """テンプレート関連の例外。"""


class ExportError(OCRAutomationError):
    """ファイル出力に関する例外。"""


class PrintError(OCRAutomationError):
    """印刷に関する例外。"""
