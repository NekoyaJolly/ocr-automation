import sys
from pathlib import Path
from app.core.model_manager import ModelManager, MODELS_INFO


def test_get_models_dir():
    models_dir = ModelManager.get_models_dir()
    assert isinstance(models_dir, Path)
    assert models_dir.name == "models"
    assert "ocr-automation" in str(models_dir).lower()


def test_get_fallback_dir():
    fb_dir = ModelManager.get_fallback_dir()
    assert isinstance(fb_dir, Path)
    assert fb_dir.name == "model"


def test_check_models():
    # 開発環境では vendor/ndlocr_lite/src/model にモデルがあるため True になるはず
    assert ModelManager.check_models() is True


def test_get_model_path():
    for name in MODELS_INFO:
        path = ModelManager.get_model_path(name)
        assert isinstance(path, Path)
        # 開発環境ではフォールバック先を指しているはず
        assert path.exists()
