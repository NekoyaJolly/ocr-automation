"""OCRモデル（ONNXファイル）のダウンロード・配置管理を行うモジュール。"""

import hashlib
import logging
import os
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

MODELS_INFO = {
    "deim-s-1024x1024.onnx": {
        "sha256": "c156ce0c4e704bc3bf7e4016d0a87b949cffa8b3724f4b4cc696b8284c3c7373",
        "size": 40256763,
    },
    "parseq-ndl-16x256-30-tiny-192epoch-tegaki3.onnx": {
        "sha256": "0bc344b883cfb11f61e15bd02044dcf92997aef1f7dce84419c3aa3c3c677d54",
        "size": 35848117,
    },
    "parseq-ndl-16x384-50-tiny-146epoch-tegaki2.onnx": {
        "sha256": "1a60e88c9ffeaefdfe286677146f39fdeb4d0e1acd94ccd974c8943f761d9a08",
        "size": 36920058,
    },
    "parseq-ndl-16x768-100-tiny-165epoch-tegaki2.onnx": {
        "sha256": "712c7184a0a80a9048a5aefbfacd63876bacfb1c8d4d2f5c252dc39ad12bc3dd",
        "size": 40984184,
    },
}

DEFAULT_BASE_URL = "https://github.com/jolly-app/ocr-automation-v1/releases/download/v1.0.0-models/"


class ModelManager:
    """ONNXモデルのローカル配置およびダウンロード状況を管理するクラス。"""

    @staticmethod
    def get_models_dir() -> Path:
        """OS推奨のユーザーアプリケーションデータ領域のモデル保存フォルダを取得する。"""
        if sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path.home() / ".local" / "share"
        return base / "ocr-automation" / "models"

    @classmethod
    def get_fallback_dir(cls) -> Path:
        """バンドル（ローカル開発環境）内のモデルフォルダを取得する。"""
        return Path(__file__).resolve().parent.parent.parent / "vendor" / "ndlocr_lite" / "src" / "model"

    @classmethod
    def check_models(cls) -> bool:
        """モデルがすべて揃っているか確認する（外部フォルダ、またはバンドルフォルダ）。"""
        # 1. 外部保存先の確認
        ext_dir = cls.get_models_dir()
        ext_ok = True
        for name in MODELS_INFO:
            if not (ext_dir / name).exists():
                ext_ok = False
                break
        if ext_ok:
            return True

        # 2. バンドルフォールバックの確認 (ローカル開発時や同梱パッケージ用)
        fb_dir = cls.get_fallback_dir()
        fb_ok = True
        for name in MODELS_INFO:
            if not (fb_dir / name).exists():
                fb_ok = False
                break
        return fb_ok

    @classmethod
    def get_model_path(cls, model_name: str) -> Path:
        """指定されたモデルファイルの絶対パスを取得する。"""
        # 外部ディレクトリに存在する場合はそれを優先
        ext_path = cls.get_models_dir() / model_name
        if ext_path.exists():
            return ext_path

        # なければバンドル（フォールバック）を返す
        return cls.get_fallback_dir() / model_name

    @classmethod
    def download_models(
        cls,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        """すべてのモデルファイルをダウンロードする。

        progress_callback は (filename, bytes_downloaded, total_bytes) を引数に取る関数。
        """
        dest_dir = cls.get_models_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)

        for name, info in MODELS_INFO.items():
            target_path = dest_dir / name
            if target_path.exists():
                # 簡易ハッシュチェック
                if cls._verify_file_hash(target_path, info["sha256"]):
                    logger.info(f"モデルファイルは既に存在し、整合性が確認されました: {name}")
                    continue
                else:
                    logger.warning(f"モデルファイルの整合性エラー。再ダウンロードします: {name}")
                    target_path.unlink()

            url = base_url + name
            temp_path = dest_dir / f"{name}.tmp"

            logger.info(f"モデルのダウンロードを開始します: {url}")
            try:
                # カスタム User-Agent を設定してダウンロード
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req) as response:
                    total_size = int(response.info().get("Content-Length", info["size"]))
                    downloaded = 0
                    block_size = 8192
                    sha256 = hashlib.sha256()

                    with open(temp_path, "wb") as f:
                        while True:
                            buffer = response.read(block_size)
                            if not buffer:
                                break
                            downloaded += len(buffer)
                            f.write(buffer)
                            sha256.update(buffer)

                            if progress_callback:
                                progress_callback(name, downloaded, total_size)

                    # ダウンロード完了後の整合性チェック
                    calc_hash = sha256.hexdigest()
                    if calc_hash != info["sha256"]:
                        raise ValueError(
                            f"ダウンロードされたファイルのハッシュが一致しません。 "
                            f"期待値: {info['sha256']}, 算出値: {calc_hash}"
                        )

                    temp_path.rename(target_path)
                    logger.info(f"モデルファイルのダウンロード完了: {target_path}")

            except Exception as e:
                if temp_path.exists():
                    temp_path.unlink()
                logger.error(f"モデルファイルのダウンロード中にエラーが発生しました: {name}", exc_info=True)
                raise e

    @staticmethod
    def _verify_file_hash(filepath: Path, expected_sha256: str) -> bool:
        """ファイルのハッシュ値を検証する。"""
        sha256 = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                while True:
                    data = f.read(65536)
                    if not data:
                        break
                    sha256.update(data)
            return sha256.hexdigest() == expected_sha256
        except Exception:
            return False
