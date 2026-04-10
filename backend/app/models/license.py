"""ライセンス関連のデータモデル。"""

from datetime import datetime

from pydantic import BaseModel


class LicenseDocument(BaseModel):
    """Firestore に保存されるライセンスドキュメント。"""

    id: str
    company_name: str
    contact_email: str = ""
    is_active: bool = True
    created_at: datetime | None = None
    expires_at: datetime | None = None
    monthly_quota: int = 1000
    current_month_usage: int = 0
    current_month_period: str = ""  # "2026-04" 形式
    notes: str = ""


class LicenseInfo(BaseModel):
    """API レスポンス用のライセンス情報。"""

    is_valid: bool
    company_name: str = ""
    expires_at: datetime | None = None
    monthly_quota: int = 0
    used_this_month: int = 0
    last_verified_at: datetime | None = None


class LicenseVerifyResponse(BaseModel):
    """ライセンス検証レスポンス。"""

    is_valid: bool
    company_name: str = ""
    expires_at: datetime | None = None
    monthly_quota: int = 0
    used_this_month: int = 0
    last_verified_at: datetime | None = None


class ErrorResponse(BaseModel):
    """エラーレスポンス。"""

    error: str
    message: str
