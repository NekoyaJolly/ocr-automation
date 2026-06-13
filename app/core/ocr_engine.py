"""OCR エンジンの抽象インターフェースおよび NDL OCR Lite 実装。"""

import logging
import sys
import time
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.exceptions import OCREngineInitError, OCRProcessError
from app.models.ocr_result_model import OCRBlock, OCRResult

logger = logging.getLogger(__name__)


class OCREngine(ABC):
    """OCR エンジンの抽象基底クラス。"""

    @abstractmethod
    def process(self, image_path: Path) -> OCRResult:
        """画像ファイルを OCR 処理し結果を返す。

        Args:
            image_path: 処理対象の画像ファイルパス

        Returns:
            OCR 結果オブジェクト

        Raises:
            OCRProcessError: OCR 処理に失敗した場合
        """
        ...


class NDLOCRLiteEngine(OCREngine):
    """NDL OCR Lite を同一プロセス内で import して使用する OCR エンジン。

    vendor/ndlocr_lite/src/ のモジュールを直接利用し、
    検出 (DEIM) → 文字認識 (PaRSeq) のパイプラインを実行する。
    """

    def __init__(self) -> None:
        """エンジンを初期化し、モデルをロードする。

        Raises:
            OCREngineInitError: モデルファイルが見つからない場合など
        """
        self._src_dir = Path(__file__).resolve().parent.parent.parent / "vendor" / "ndlocr_lite" / "src"
        if not self._src_dir.exists():
            raise OCREngineInitError(
                f"NDL OCR Lite のソースディレクトリが見つかりません: {self._src_dir}"
            )

        # NDL OCR Lite のモジュールを import するため sys.path に追加
        src_str = str(self._src_dir)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)

        try:
            self._initialize_models()
        except Exception as e:
            raise OCREngineInitError(f"モデルの初期化に失敗しました: {e}") from e

    def _initialize_models(self) -> None:
        """DEIM 検出器と PaRSeq 認識器をロードする。"""
        from deim import DEIM
        from parseq import PARSEQ
        from yaml import safe_load

        from app.core.model_manager import ModelManager

        config_dir = self._src_dir / "config"

        # 検出器
        det_weights = str(ModelManager.get_model_path("deim-s-1024x1024.onnx"))
        det_classes = str(config_dir / "ndl.yaml")
        self._detector = DEIM(
            model_path=det_weights,
            class_mapping_path=det_classes,
            score_threshold=0.2,
            conf_threshold=0.25,
            iou_threshold=0.2,
            device="cpu",
        )

        # 認識器（3種: 30文字/50文字/100文字用）
        rec_classes = str(config_dir / "NDLmoji.yaml")
        with open(rec_classes, encoding="utf-8") as f:
            charobj = safe_load(f)
        charlist = list(charobj["model"]["charset_train"])

        self._recognizer30 = PARSEQ(
            model_path=str(ModelManager.get_model_path("parseq-ndl-16x256-30-tiny-192epoch-tegaki3.onnx")),
            charlist=charlist,
            device="cpu",
        )
        self._recognizer50 = PARSEQ(
            model_path=str(ModelManager.get_model_path("parseq-ndl-16x384-50-tiny-146epoch-tegaki2.onnx")),
            charlist=charlist,
            device="cpu",
        )
        self._recognizer100 = PARSEQ(
            model_path=str(ModelManager.get_model_path("parseq-ndl-16x768-100-tiny-165epoch-tegaki2.onnx")),
            charlist=charlist,
            device="cpu",
        )

        logger.info("NDL OCR Lite モデルの初期化が完了しました")

    def process(self, image_path: Path) -> OCRResult:
        """画像ファイルを OCR 処理し結果を返す。

        NDL OCR Lite の process() 関数のロジックを再現し、
        検出 → 認識 → 構造化データ生成を行う。

        Args:
            image_path: 処理対象の画像ファイルパス

        Returns:
            OCR 結果オブジェクト

        Raises:
            OCRProcessError: OCR 処理に失敗した場合
        """
        if not image_path.exists():
            raise OCRProcessError(f"画像ファイルが見つかりません: {image_path}")

        try:
            return self._process_image(image_path)
        except OCRProcessError:
            raise
        except Exception as e:
            logger.exception("OCR 処理中にエラーが発生しました")
            raise OCRProcessError(f"OCR 処理に失敗しました: {e}") from e

    def _process_image(self, image_path: Path) -> OCRResult:
        """画像の OCR 処理を実行する内部メソッド。"""
        from ndl_parser import convert_to_xml_string3
        from ocr import RecogLine, process_cascade
        from reading_order.xy_cut.eval import eval_xml

        start_time = time.time()

        # 画像を読み込み
        pil_image = Image.open(image_path).convert("RGB")
        img = np.array(pil_image)
        img_h, img_w = img.shape[:2]
        img_name = image_path.name

        # 検出
        detections = self._detector.detect(img)
        classes_list = list(self._detector.classes.values())

        # 検出結果を XML に変換
        result_obj: list[dict[int, Any]] = [dict(), dict()]
        result_obj[0][0] = list()
        for i in range(17):
            result_obj[1][i] = []
        for det in detections:
            xmin, ymin, xmax, ymax = det["box"]
            conf = det["confidence"]
            char_count = det["pred_char_count"]
            if det["class_index"] == 0:
                result_obj[0][0].append([xmin, ymin, xmax, ymax])
            result_obj[1][det["class_index"]].append(
                [xmin, ymin, xmax, ymax, conf, char_count]
            )

        xml_str = convert_to_xml_string3(img_w, img_h, img_name, classes_list, result_obj)
        xml_str = f"<OCRDATASET>{xml_str}</OCRDATASET>"
        root = ET.fromstring(xml_str)
        eval_xml(root, logger=None)

        # 行画像の切り出し
        all_line_obj: list[Any] = []
        tate_line_cnt = 0
        all_line_cnt = 0
        blocks: list[OCRBlock] = []

        for idx, line_elem in enumerate(root.findall(".//LINE")):
            xmin = int(line_elem.get("X", "0"))
            ymin = int(line_elem.get("Y", "0"))
            line_w = int(line_elem.get("WIDTH", "0"))
            line_h = int(line_elem.get("HEIGHT", "0"))
            try:
                pred_char_cnt = float(line_elem.get("PRED_CHAR_CNT", "100"))
            except (TypeError, ValueError):
                pred_char_cnt = 100.0

            if line_h > line_w:
                tate_line_cnt += 1
            all_line_cnt += 1

            line_img = img[ymin : ymin + line_h, xmin : xmin + line_w, :]
            line_recog_obj = RecogLine(line_img, idx, pred_char_cnt)
            all_line_obj.append(line_recog_obj)

        # LINE が無いが検出がある場合のフォールバック
        if len(all_line_obj) == 0 and len(detections) > 0:
            page = root.find("PAGE")
            for idx, det in enumerate(detections):
                xmin_f, ymin_f, xmax_f, ymax_f = det["box"]
                line_w = int(xmax_f - xmin_f)
                line_h = int(ymax_f - ymin_f)
                if line_w > 0 and line_h > 0:
                    if page is not None:
                        line_elem = ET.SubElement(page, "LINE")
                        line_elem.set("TYPE", "本文")
                        line_elem.set("X", str(int(xmin_f)))
                        line_elem.set("Y", str(int(ymin_f)))
                        line_elem.set("WIDTH", str(line_w))
                        line_elem.set("HEIGHT", str(line_h))
                        line_elem.set("CONF", f"{det['confidence']:0.3f}")
                        pred_char_cnt = det.get("pred_char_count", 100.0)
                        line_elem.set("PRED_CHAR_CNT", f"{pred_char_cnt:0.3f}")
                    if line_h > line_w:
                        tate_line_cnt += 1
                    all_line_cnt += 1
                    line_img = img[int(ymin_f) : int(ymax_f), int(xmin_f) : int(xmax_f), :]
                    line_recog_obj = RecogLine(line_img, idx, pred_char_cnt)
                    all_line_obj.append(line_recog_obj)

        # 文字認識（カスケード方式）
        if all_line_obj:
            result_lines = process_cascade(
                all_line_obj,
                self._recognizer30,
                self._recognizer50,
                self._recognizer100,
                is_cascade=True,
            )
        else:
            result_lines = []

        # LINE 要素に認識結果を設定し、OCRBlock を構築
        for idx, line_elem in enumerate(root.findall(".//LINE")):
            if idx < len(result_lines):
                text = result_lines[idx]
            else:
                text = ""
            xmin = int(line_elem.get("X", "0"))
            ymin = int(line_elem.get("Y", "0"))
            line_w = int(line_elem.get("WIDTH", "0"))
            line_h = int(line_elem.get("HEIGHT", "0"))
            try:
                conf = float(line_elem.get("CONF", "0"))
            except (TypeError, ValueError):
                conf = 0.0

            blocks.append(
                OCRBlock(
                    text=text,
                    bbox=(xmin, ymin, line_w, line_h),
                    confidence=min(max(conf, 0.0), 1.0),
                )
            )

        # 縦書きが多い場合はテキスト順序を反転
        text_lines = [b.text for b in blocks]
        if all_line_cnt > 0 and tate_line_cnt / all_line_cnt > 0.5:
            text_lines = text_lines[::-1]

        raw_text = "\n".join(text_lines)
        elapsed_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"OCR 完了: {image_path.name} ({len(blocks)} ブロック, {elapsed_ms}ms)"
        )

        return OCRResult(
            source_image=image_path,
            blocks=blocks,
            raw_text=raw_text,
            processing_time_ms=elapsed_ms,
        )
