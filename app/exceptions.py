"""OCR Automation App のカスタム例外定義。"""


class OCRAutomationError(Exception):
    """アプリケーション全体の基底例外。"""


# --- OCR エンジン関連 ---
class OCREngineError(OCRAutomationError):
    """OCR エンジン処理中のエラー。"""


# --- ライセンス関連 ---
class LicenseError(OCRAutomationError):
    """ライセンス関連の基底例外。"""


class LicenseNotConfiguredError(LicenseError):
    """ライセンスキーが未設定。"""


class LicenseInvalidError(LicenseError):
    """ライセンスキーが無効。"""


class LicenseExpiredError(LicenseError):
    """ライセンスキーの有効期限切れ。"""


class LicenseQuotaExceededError(LicenseError):
    """月間利用上限を超過。"""


# --- バックエンド通信関連 ---
class BackendError(OCRAutomationError):
    """バックエンド通信の基底例外。"""


class BackendUnreachableError(BackendError):
    """バックエンドに接続不能。"""


class BackendBadRequestError(BackendError):
    """バックエンドがリクエストを拒否 (400)。"""


# --- テンプレート関連 ---
class TemplateConfigError(OCRAutomationError):
    """テンプレート設定の不備。"""


class TemplateNotFoundError(TemplateConfigError):
    """指定されたテンプレートが見つからない。"""


# --- エクスポート関連 ---
class ExportError(OCRAutomationError):
    """ファイル出力時のエラー。"""


# --- 印刷関連 ---
class PrintError(OCRAutomationError):
    """印刷処理のエラー。"""
