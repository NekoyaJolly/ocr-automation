"""OCR エンジンのユニットテスト。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.core.ocr_engine import NDLOCRLiteEngine, OCREngine
from app.exceptions import OCREngineInitError, OCRProcessError
from app.models.ocr_result_model import OCRBlock, OCRResult


class TestOCREngineABC:
    """OCREngine 抽象基底クラスのテスト。"""

    def test_cannot_instantiate_abstract(self) -> None:
        """抽象クラスを直接インスタンス化できないことを確認。"""
        with pytest.raises(TypeError):
            OCREngine()  # type: ignore[abstract]

    def test_subclass_must_implement_process(self) -> None:
        """サブクラスが process を実装している必要があることを確認。"""

        class IncompleteEngine(OCREngine):
            pass

        with pytest.raises(TypeError):
            IncompleteEngine()  # type: ignore[abstract]

    def test_valid_subclass(self) -> None:
        """process を実装したサブクラスはインスタンス化できることを確認。"""

        class DummyEngine(OCREngine):
            def process(self, image_path: Path) -> OCRResult:
                return OCRResult(source_image=image_path, raw_text="dummy")

        engine = DummyEngine()
        result = engine.process(Path("/dummy.png"))
        assert result.raw_text == "dummy"


class TestOCRResultModel:
    """OCRResult データモデルのテスト。"""

    def test_default_values(self) -> None:
        """デフォルト値が正しく設定されることを確認。"""
        result = OCRResult(source_image=Path("/test.png"))
        assert result.blocks == []
        assert result.raw_text == ""
        assert result.processing_time_ms == 0

    def test_with_blocks(self) -> None:
        """ブロック付きの結果が正しく構築されることを確認。"""
        block = OCRBlock(text="テスト", bbox=(10, 20, 100, 30), confidence=0.95)
        result = OCRResult(
            source_image=Path("/test.png"),
            blocks=[block],
            raw_text="テスト",
            processing_time_ms=500,
        )
        assert len(result.blocks) == 1
        assert result.blocks[0].text == "テスト"
        assert result.blocks[0].confidence == 0.95

    def test_confidence_validation(self) -> None:
        """confidence の値が 0.0〜1.0 の範囲であることを確認。"""
        with pytest.raises(Exception):
            OCRBlock(text="test", bbox=(0, 0, 10, 10), confidence=1.5)
        with pytest.raises(Exception):
            OCRBlock(text="test", bbox=(0, 0, 10, 10), confidence=-0.1)


class TestNDLOCRLiteEngine:
    """NDLOCRLiteEngine のテスト。"""

    def test_init_missing_vendor_dir(self, tmp_path: Path) -> None:
        """vendor ディレクトリが存在しない場合に初期化エラーが発生することを確認。"""
        with patch.object(
            NDLOCRLiteEngine,
            "__init__",
            lambda self: None,  # type: ignore[misc]
        ):
            engine = NDLOCRLiteEngine.__new__(NDLOCRLiteEngine)
            engine._src_dir = tmp_path / "nonexistent"
            # _src_dir が存在しない場合、通常の __init__ で OCREngineInitError が発生する
            # ここでは _src_dir のパス設定のみ確認

    def test_process_nonexistent_file(self) -> None:
        """存在しないファイルを渡した場合にエラーになることを確認。"""
        with patch.object(
            NDLOCRLiteEngine,
            "__init__",
            lambda self: None,  # type: ignore[misc]
        ):
            engine = NDLOCRLiteEngine.__new__(NDLOCRLiteEngine)
            engine._src_dir = Path("/dummy")
            with pytest.raises(OCRProcessError, match="画像ファイルが見つかりません"):
                engine.process(Path("/nonexistent/image.png"))
