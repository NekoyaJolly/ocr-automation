"""バックエンドのカスタム例外。"""


class BackendError(Exception):
    """バックエンドの基底例外。"""


class LicenseInvalidError(BackendError):
    """ライセンスキーが無効。"""


class LicenseExpiredError(BackendError):
    """ライセンスキーの有効期限切れ。"""


class LicenseQuotaExceededError(BackendError):
    """月間利用上限超過。"""


class RateLimitExceededError(BackendError):
    """レート制限超過。"""


class GeminiError(BackendError):
    """Gemini API 呼び出しのエラー。"""
