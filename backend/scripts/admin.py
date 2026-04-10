"""ライセンス管理 CLI スクリプト。"""

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timezone

from google.cloud.firestore import AsyncClient  # type: ignore[import-untyped]


async def create_license(
    db: AsyncClient,
    company: str,
    email: str,
    quota: int,
    expires: str,
) -> str:
    """新しいライセンスを作成する。"""
    license_key = f"OCRA-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}"

    doc = {
        "company_name": company,
        "contact_email": email,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.fromisoformat(expires).replace(tzinfo=timezone.utc),
        "monthly_quota": quota,
        "current_month_usage": 0,
        "current_month_period": datetime.now(timezone.utc).strftime("%Y-%m"),
        "notes": "",
    }

    await db.collection("licenses").document(license_key).set(doc)
    return license_key


async def disable_license(db: AsyncClient, license_key: str) -> None:
    """ライセンスを無効化する。"""
    doc_ref = db.collection("licenses").document(license_key)
    snapshot = await doc_ref.get()
    if not snapshot.exists:
        print(f"ライセンスが見つかりません: {license_key}")
        return
    await doc_ref.update({"is_active": False})
    print(f"ライセンスを無効化しました: {license_key}")


async def show_usage(db: AsyncClient, license_key: str) -> None:
    """ライセンスの利用状況を表示する。"""
    doc_ref = db.collection("licenses").document(license_key)
    snapshot = await doc_ref.get()
    if not snapshot.exists:
        print(f"ライセンスが見つかりません: {license_key}")
        return
    data = snapshot.to_dict()
    print(f"会社名: {data.get('company_name')}")
    print(f"有効: {data.get('is_active')}")
    print(f"有効期限: {data.get('expires_at')}")
    print(f"月間上限: {data.get('monthly_quota')}")
    print(f"当月利用: {data.get('current_month_usage')}")
    print(f"当月期間: {data.get('current_month_period')}")


async def list_licenses(db: AsyncClient) -> None:
    """全ライセンスを一覧表示する。"""
    docs = db.collection("licenses").stream()
    count = 0
    async for doc in docs:
        data = doc.to_dict()
        status = "有効" if data.get("is_active") else "無効"
        print(f"  {doc.id[:20]}...  {data.get('company_name', '?'):20s}  [{status}]  {data.get('current_month_usage', 0)}/{data.get('monthly_quota', 0)}")
        count += 1
    print(f"\n合計: {count} ライセンス")


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR Automation ライセンス管理 CLI")
    subparsers = parser.add_subparsers(dest="command")

    create_parser = subparsers.add_parser("create-license", help="新規ライセンス作成")
    create_parser.add_argument("--company", required=True)
    create_parser.add_argument("--email", default="")
    create_parser.add_argument("--quota", type=int, default=1000)
    create_parser.add_argument("--expires", required=True, help="YYYY-MM-DD")

    disable_parser = subparsers.add_parser("disable-license", help="ライセンス無効化")
    disable_parser.add_argument("license_key")

    usage_parser = subparsers.add_parser("show-usage", help="利用状況表示")
    usage_parser.add_argument("--license", required=True)

    subparsers.add_parser("list", help="全ライセンス一覧")

    args = parser.parse_args()

    import os
    project_id = os.environ.get("BACKEND_PROJECT_ID", "ocr-automation-dev")

    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        db = AsyncClient(project=project_id)
    else:
        db = AsyncClient(project=project_id)

    if args.command == "create-license":
        key = asyncio.run(create_license(db, args.company, args.email, args.quota, args.expires))
        print(f"\nライセンスキー: {key}")
    elif args.command == "disable-license":
        asyncio.run(disable_license(db, args.license_key))
    elif args.command == "show-usage":
        asyncio.run(show_usage(db, args.license))
    elif args.command == "list":
        asyncio.run(list_licenses(db))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
