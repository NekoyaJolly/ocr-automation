"""OCR Automation アプリケーション エントリポイント。

GUI モード (デフォルト) と CLI モードを切り替えられる。

使い方:
    GUI 起動:  python -m app
    CLI 起動:  python -m app --cli <image_path> [-o output.txt]
"""

import argparse
import sys
from pathlib import Path


def _run_cli(args: argparse.Namespace) -> None:
    """Phase 1 相当の CLI モードを実行する。"""
    from app.infrastructure.logger import setup_logger

    setup_logger(level="DEBUG" if args.verbose else "INFO")

    image_path: Path = args.image
    if not image_path.exists():
        print(f"エラー: 画像ファイルが見つかりません: {image_path}", file=sys.stderr)
        sys.exit(1)

    supported_ext = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".jp2", ".bmp"}
    if image_path.suffix.lower() not in supported_ext:
        print(
            f"エラー: サポートされていない画像形式です: {image_path.suffix}",
            file=sys.stderr,
        )
        sys.exit(1)

    from app.core.model_manager import ModelManager
    if not ModelManager.check_models():
        print("OCRモデルが見つかりません。ダウンロードを開始します...", file=sys.stderr)
        try:
            last_file = ""
            def cli_callback(filename, downloaded, total):
                nonlocal last_file
                if filename != last_file:
                    if last_file:
                        print(file=sys.stderr)
                    last_file = filename
                percent = int(downloaded / total * 100) if total > 0 else 0
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                print(f"\rダウンロード中: {filename} [{percent}%] ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end="", file=sys.stderr)

            ModelManager.download_models(progress_callback=cli_callback)
            print(file=sys.stderr)
            print("モデルのダウンロードが完了しました。", file=sys.stderr)
        except Exception as e:
            print(f"\nエラー: モデルのダウンロードに失敗しました: {e}", file=sys.stderr)
            sys.exit(1)

    from app.core.ocr_engine import NDLOCRLiteEngine
    from app.exceptions import OCRAutomationError

    try:
        engine = NDLOCRLiteEngine()
    except OCRAutomationError as e:
        print(f"エラー: OCR エンジンの初期化に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        result = engine.process(image_path)
    except OCRAutomationError as e:
        print(f"エラー: OCR 処理に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    output_text = result.raw_text
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_text, encoding="utf-8")
        print(f"結果を保存しました: {args.output}", file=sys.stderr)
    else:
        print(output_text)

    print(
        f"--- OCR 完了: {len(result.blocks)} ブロック, "
        f"{result.processing_time_ms}ms ---",
        file=sys.stderr,
    )


def _run_gui() -> None:
    """GUI モードでアプリケーションを起動する。"""
    from PySide6.QtWidgets import QApplication

    from app.controllers.app_controller import AppController
    from app.core.ocr_engine import NDLOCRLiteEngine
    from app.exceptions import OCRAutomationError
    from app.gui.main_window import MainWindow
    from app.infrastructure.logger import setup_logger
    from app.infrastructure.paths import ensure_app_dirs
    from app.infrastructure.settings_store import SettingsStore

    ensure_app_dirs()

    settings_store = SettingsStore()
    settings = settings_store.load()

    setup_logger(level=settings.log_level, enable_file=True)

    app = QApplication(sys.argv)
    app.setApplicationName("OCR Automation")

    from app.core.model_manager import ModelManager
    if not ModelManager.check_models():
        from app.gui.model_download_dialog import ModelDownloadDialog
        dialog = ModelDownloadDialog()
        if not dialog.start_download():
            sys.exit(0)

    try:
        ocr_engine = NDLOCRLiteEngine()
    except OCRAutomationError as e:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(
            None,
            "起動エラー",
            f"OCR エンジンの初期化に失敗しました:\n{e}\n\n"
            "vendor/ndlocr_lite/ が正しく配置されているか確認してください。",
        )
        sys.exit(1)

    controller = AppController(settings, ocr_engine)
    window = MainWindow(controller, settings_store, settings)
    window.show()

    sys.exit(app.exec())


def main() -> None:
    """メインエントリポイント。引数に応じて CLI / GUI を切り替える。"""
    parser = argparse.ArgumentParser(
        description="OCR Automation - 手書き画像の OCR 自動処理ツール",
    )
    subparsers = parser.add_subparsers(dest="command")

    cli_parser = subparsers.add_parser("cli", help="CLI モードで画像を OCR 処理する")
    cli_parser.add_argument(
        "image",
        type=Path,
        help="OCR 処理する画像ファイルのパス",
    )
    cli_parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="結果テキストの出力先ファイルパス（省略時は標準出力）",
    )
    cli_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="詳細ログを出力する",
    )

    args = parser.parse_args()

    if args.command == "cli":
        _run_cli(args)
    else:
        _run_gui()


if __name__ == "__main__":
    main()
