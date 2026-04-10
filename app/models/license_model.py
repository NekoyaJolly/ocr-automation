"""ライセンス情報のデータモデル。"""

from datetime import datetime

from pydantic import BaseModel


class LicenseInfo(BaseModel):
    """バックエンドから返るライセンス情報。"""

    company_name: str
    is_valid: bool
    expires_at: datetime | None = None
    monthly_quota: int = 0
    used_this_month: int = 0
    last_verified_at: datetime | None = None
