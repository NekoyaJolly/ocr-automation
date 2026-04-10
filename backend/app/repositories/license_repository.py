"""ライセンスの Firestore リポジトリ。"""

from datetime import UTC, datetime

from google.cloud.firestore import AsyncClient  # type: ignore[import-untyped]

from app.models.license import LicenseDocument


class LicenseRepository:
    """Firestore の licenses コレクションにアクセスする。"""

    COLLECTION = "licenses"

    def __init__(self, db: AsyncClient) -> None:
        self._db = db

    async def find(self, license_key: str) -> LicenseDocument | None:
        """ライセンスキーでドキュメントを検索する。"""
        doc_ref = self._db.collection(self.COLLECTION).document(license_key)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict()
        data["id"] = snapshot.id
        return LicenseDocument(**data)

    async def increment_usage(self, license_key: str) -> None:
        """当月の利用数をインクリメントする。月が変わっていればリセット。"""
        current_period = datetime.now(UTC).strftime("%Y-%m")
        doc_ref = self._db.collection(self.COLLECTION).document(license_key)

        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return

        data = snapshot.to_dict()
        if data.get("current_month_period") != current_period:
            await doc_ref.update({
                "current_month_period": current_period,
                "current_month_usage": 1,
            })
        else:
            from google.cloud.firestore import Increment  # type: ignore[import-untyped]
            await doc_ref.update({
                "current_month_usage": Increment(1),
            })

    async def create(self, license_key: str, doc: LicenseDocument) -> None:
        """新しいライセンスドキュメントを作成する。"""
        doc_ref = self._db.collection(self.COLLECTION).document(license_key)
        data = doc.model_dump(exclude={"id"})
        await doc_ref.set(data)

    async def update_active(self, license_key: str, is_active: bool) -> None:
        """ライセンスの有効/無効を更新する。"""
        doc_ref = self._db.collection(self.COLLECTION).document(license_key)
        await doc_ref.update({"is_active": is_active})
