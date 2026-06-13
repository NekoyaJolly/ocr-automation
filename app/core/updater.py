"""アプリケーションの自動アップデートチェックを行うモジュール。"""

import json
import logging
import urllib.request
import sys
from typing import Any, Optional
from app import __version__

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com/repos/jolly-app/ocr-automation-v1/releases/latest"


def parse_version(version_str: str) -> tuple[int, ...]:
    """バージョン文字列（例: 'v1.2.3' または '1.2.3'）を比較可能なタプルに変換する。"""
    clean_str = version_str.strip().lower()
    if clean_str.startswith("v"):
        clean_str = clean_str[1:]
    try:
        return tuple(map(int, clean_str.split(".")))
    except ValueError:
        return (0,)


def check_for_update(api_url: str = GITHUB_API_URL) -> Optional[dict[str, Any]]:
    """最新バージョンをチェックする。アップデートがある場合は詳細を辞書で返し、なければ None を返す。"""
    logger.info("アップデートのチェックを開始します...")
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))

        tag_name = data.get("tag_name", "")
        if not tag_name:
            logger.warning("リリース情報に tag_name が見つかりませんでした。")
            return None

        current_ver = parse_version(__version__)
        latest_ver = parse_version(tag_name)

        if latest_ver <= current_ver:
            logger.info(f"アプリは最新状態です。現在のバージョン: {__version__}, 最新のリリース: {tag_name}")
            return None

        logger.info(f"新しいバージョンが利用可能です: {tag_name}")

        # OSに応じたダウンロード先アセットを探す
        download_url = ""
        assets = data.get("assets", [])
        target_name = "ocr-automation-win.zip" if sys.platform == "win32" else "ocr-automation-mac.zip"

        for asset in assets:
            if asset.get("name") == target_name:
                download_url = asset.get("browser_download_url", "")
                break

        return {
            "version": tag_name,
            "html_url": data.get("html_url", ""),
            "download_url": download_url,
            "body": data.get("body", "リリースノートはありません。"),
        }

    except Exception as e:
        logger.warning(f"アップデートチェックに失敗しました (オフラインまたは接続エラー): {e}")
        return None
