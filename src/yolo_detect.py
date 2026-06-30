"""
src/yolo_detect.py
Runs YOLOv8 nano object detection on all images downloaded in Task 1,
classifies each image into one of four categories, and writes results
to a CSV file for warehouse integration.

Usage:
    python -m src.yolo_detect
"""

import csv
import logging
from pathlib import Path

from ultralytics import YOLO

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("yolo_detect")

IMAGES_ROOT = Path("data/raw/images")
OUTPUT_CSV = Path("data/yolo_results.csv")

# Classes from the COCO dataset (what yolov8n.pt is trained on) that we
# treat as "product-like" objects for the classification scheme below.
PRODUCT_LIKE_CLASSES = {
    "bottle", "cup", "wine glass", "bowl", "box", "suitcase",
    "handbag", "backpack", "book",
}

CONFIDENCE_THRESHOLD = 0.35


def classify_image(detected_classes: set[str]) -> str:
    """
    Apply the project's 4-category classification scheme:
      promotional    - person + product-like object
      product_display - product-like object, no person
      lifestyle      - person, no product-like object
      other          - neither
    """
    has_person = "person" in detected_classes
    has_product = bool(detected_classes & PRODUCT_LIKE_CLASSES)

    if has_person and has_product:
        return "promotional"
    if has_product and not has_person:
        return "product_display"
    if has_person and not has_product:
        return "lifestyle"
    return "other"


def iter_images():
    """Yield (channel_name, message_id, image_path) for every downloaded image."""
    if not IMAGES_ROOT.exists():
        logger.warning("No images directory found at %s", IMAGES_ROOT)
        return
    for channel_dir in sorted(IMAGES_ROOT.iterdir()):
        if not channel_dir.is_dir():
            continue
        for image_path in sorted(channel_dir.glob("*.jpg")):
            message_id = image_path.stem
            yield channel_dir.name, message_id, image_path


def run_detection():
    model = YOLO("yolov8n.pt")

    rows = []
    total_images = 0
    failed_images = 0

    for channel_name, message_id, image_path in iter_images():
        total_images += 1
        try:
            results = model(str(image_path), verbose=False)
        except (FileNotFoundError, OSError) as e:
            logger.error("Could not read image %s: %s", image_path, e)
            failed_images += 1
            continue
        except Exception as e:  # noqa: BLE001 - corrupt/unsupported image formats
            logger.error("YOLO inference failed for %s: %s", image_path, e)
            failed_images += 1
            continue

        result = results[0]
        detected_classes = set()

        if result.boxes is None or len(result.boxes) == 0:
            rows.append({
                "message_id": message_id,
                "channel_name": channel_name,
                "detected_class": None,
                "confidence_score": None,
                "image_category": "other",
            })
            continue

        for box in result.boxes:
            class_id = int(box.cls[0])
            class_name = model.names[class_id]
            confidence = float(box.conf[0])

            if confidence < CONFIDENCE_THRESHOLD:
                continue

            detected_classes.add(class_name)
            rows.append({
                "message_id": message_id,
                "channel_name": channel_name,
                "detected_class": class_name,
                "confidence_score": round(confidence, 4),
                "image_category": None,  # filled in below once all detections are known
            })

        category = classify_image(detected_classes)
        # backfill the category for every detection row from this image
        for row in rows[-len(detected_classes) if detected_classes else 0:]:
            row["image_category"] = category
        if not detected_classes:
            rows.append({
                "message_id": message_id,
                "channel_name": channel_name,
                "detected_class": None,
                "confidence_score": None,
                "image_category": category,
            })

        logger.info(
            "Processed %s/%s: %d detections -> %s",
            channel_name, message_id, len(detected_classes), category,
        )

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["message_id", "channel_name", "detected_class",
                        "confidence_score", "image_category"],
        )
        writer.writeheader()
        writer.writerows(rows)

    logger.info(
        "Done. Processed %d images (%d failed), wrote %d rows to %s",
        total_images, failed_images, len(rows), OUTPUT_CSV,
    )


if __name__ == "__main__":
    run_detection()