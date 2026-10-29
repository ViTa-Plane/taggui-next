import json
from pathlib import Path
from PIL import Image
from PySide6.QtCore import QObject, Slot, Signal, Property
from PySide6.QtWidgets import QFileDialog
import hashlib


class TagGUIBridge(QObject):
    pathChanged = Signal(str)

    def __init__(self, dataset_path=None):
        super().__init__()

        # Check global config or local fallback for the last opened dataset path
        initial_path = dataset_path
        if not initial_path:
            config_path = Path.cwd() / "last_dataset.json"
            if config_path.exists():
                try:
                    config_data = json.loads(config_path.read_text(encoding="utf-8"))
                    saved_path = Path(config_data.get("last_path", ""))
                    if saved_path.exists():
                        initial_path = saved_path
                except Exception as e:
                    print(f"[Backend] Failed to load last_dataset.json: {e}")

        self._dataset_path = (
            Path(initial_path) if initial_path else Path.cwd() / "sample_dataset"
        )
        self._dataset_path.mkdir(exist_ok=True)

        self.thumbs_dir = self._dataset_path / ".taggui_thumbs"
        self.thumbs_dir.mkdir(exist_ok=True)

        # Save current path as last opened
        self._save_last_path_config()

        # Run automatic thumbnail cleanup on startup
        self.cleanupThumbnails()

    def _save_last_path_config(self):
        try:
            config_path = Path.cwd() / "last_dataset.json"
            config_path.write_text(json.dumps({"last_path": str(self._dataset_path.resolve())}, indent=2),
                                   encoding="utf-8")
        except Exception as e:
            print(f"[Backend] Failed to save last_dataset.json: {e}")

    @Property(str, notify=pathChanged)
    def dataset_path_str(self):
        return str(self._dataset_path.resolve())

    @Slot(result=str)
    def getDatasetImages(self):
        return json.dumps(self._scan_images())

    @Slot(result=str)
    def browseDatasetFolder(self):
        dir_path = QFileDialog.getExistingDirectory(None, "Select Dataset Directory")
        if dir_path:
            self._dataset_path = Path(dir_path)
            self.thumbs_dir = self._dataset_path / ".taggui_thumbs"
            self.thumbs_dir.mkdir(exist_ok=True)
            print(f"[Backend] Switched dataset path to: {self._dataset_path}")

            # Automatically run garbage collection on thumbnail folder
            self.cleanupThumbnails()

            # Save to last dataset config
            self._save_last_path_config()

            self.pathChanged.emit(str(self._dataset_path.resolve()))
            return json.dumps(self._scan_images())
        return ""

    @Slot(result=str)
    def getDatasetSettings(self):
        settings_path = self._dataset_path / "settings.json"
        if settings_path.exists():
            try:
                return settings_path.read_text(encoding="utf-8")
            except Exception as e:
                print(f"[Backend] Failed to read settings.json: {e}")
        # Default settings including thresholds for local auto-tagging
        return json.dumps({
            "keywords": "",
            "general_threshold": 0.35,
            "character_threshold": 0.85
        })

    @Slot(str)
    def saveDatasetSettings(self, settings_json_str):
        settings_path = self._dataset_path / "settings.json"
        try:
            # Accepts either a raw string of keywords or a full JSON settings object from UI
            if settings_json_str.strip().startswith("{"):
                data = json.loads(settings_json_str)
            else:
                # Fallback if only keywords string was passed
                existing = {}
                if settings_path.exists():
                    existing = json.loads(settings_path.read_text(encoding="utf-8"))
                existing["keywords"] = settings_json_str
                data = existing

            settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print("[Backend] Dataset settings saved successfully.")
        except Exception as e:
            print(f"[Backend] Failed to write settings.json: {e}")

    def _scan_images(self):
        images = []
        valid_exts = {".png", ".jpg", ".jpeg", ".webp"}

        for f in self._dataset_path.rglob("*"):
            if f.is_file() and f.suffix.lower() in valid_exts:
                if ".taggui_thumbs" in f.parts:
                    continue

                txt_path = f.with_suffix(".txt")
                tags_text = (
                    txt_path.read_text(encoding="utf-8").strip()
                    if txt_path.exists()
                    else ""
                )

                thumb_path = self._get_thumbnail_path(f)

                if not thumb_path.exists() or thumb_path.stat().st_mtime < f.stat().st_mtime:
                    try:
                        with Image.open(f) as img:
                            img.thumbnail((300, 300))
                            if img.mode in ("RGBA", "P"):
                                img = img.convert("RGB")
                            thumb_path.parent.mkdir(exist_ok=True, parents=True)
                            img.save(thumb_path, "JPEG", quality=85)
                    except Exception as e:
                        print(f"[Backend] Thumbnail generation failed for {f.name}: {e}")

                rel_path = f.relative_to(self._dataset_path)

                images.append({
                    "filename": f.name,
                    "relative_path": str(rel_path).replace("\\", "/"),
                    "url": thumb_path.as_uri(),
                    "full_url": f.as_uri(),
                    "tags": [t.strip() for t in tags_text.split(",") if t.strip()],
                })

        print(f"[Backend] Loaded {len(images)} dataset images.")
        return images

    @Slot(str, str)
    def saveImageTags(self, relative_path, tags_comma_separated):
        txt_path = self._dataset_path / Path(relative_path).with_suffix(".txt")
        txt_path.write_text(tags_comma_separated, encoding="utf-8")

    @Slot(str)
    def saveBatchImageTags(self, updates_json_str):
        try:
            updates = json.loads(updates_json_str)
            for rel_path, tags_str in updates.items():
                txt_path = self._dataset_path / Path(rel_path).with_suffix(".txt")
                txt_path.write_text(tags_str, encoding="utf-8")
        except Exception as e:
            print(f"[Backend] Batch save failed: {e}")

    @Slot(str, result=int)
    def estimateTokens(self, tags_string):
        tokens = [t.strip() for t in tags_string.split(",") if t.strip()]
        return int(len(tokens) * 1.5)

    @Slot(str, result=bool)
    def deleteImageAndTags(self, relative_path):
        try:
            img_path = self._dataset_path / relative_path
            txt_path = img_path.with_suffix(".txt")

            backup_dir = self._dataset_path / ".taggui_backup"
            backup_dir.mkdir(exist_ok=True)

            if img_path.exists():
                import shutil
                shutil.move(str(img_path), str(backup_dir / img_path.name))
            if txt_path.exists():
                import shutil
                shutil.move(str(txt_path), str(backup_dir / txt_path.name))

            print(f"[Backend] Moved to backup/trash: {img_path.name}")
            return True
        except Exception as e:
            print(f"[Backend] Failed to delete image {relative_path}: {e}")
            return False

    @Slot(str, result=bool)
    def restoreImageAndTags(self, relative_path):
        try:
            backup_dir = self._dataset_path / ".taggui_backup"
            img_name = Path(relative_path).name
            txt_name = Path(relative_path).with_suffix(".txt").name

            backup_img = backup_dir / img_name
            backup_txt = backup_dir / txt_name

            target_img = self._dataset_path / relative_path
            target_txt = target_img.with_suffix(".txt")

            target_img.parent.mkdir(parents=True, exist_ok=True)

            import shutil
            if backup_img.exists():
                shutil.move(str(backup_img), str(target_img))
            if backup_txt.exists():
                shutil.move(str(backup_txt), str(target_txt))

            print(f"[Backend] Restored: {img_name}")
            return True
        except Exception as e:
            print(f"[Backend] Failed to restore image {relative_path}: {e}")
            return False

    @Slot()
    def openDatasetInExplorer(self):
        try:
            if hasattr(self, '_dataset_path') and self._dataset_path:
                from PySide6.QtGui import QDesktopServices
                from PySide6.QtCore import QUrl
                path_obj = Path(self._dataset_path)
                if path_obj.exists():
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path_obj)))
                    print(f"[Backend] Opened folder in explorer: {path_obj}")
        except Exception as e:
            print(f"[Backend] Failed to open dataset folder: {e}")

    def _get_thumbnail_path(self, img_path: Path) -> Path:
        """Generates a stable, unique thumbnail path based on the image's relative path and mtime."""
        thumbs_dir = self._dataset_path / ".taggui_thumbs"
        thumbs_dir.mkdir(exist_ok=True, parents=True)

        rel_path_str = str(img_path.relative_to(self._dataset_path))
        path_hash = hashlib.md5(rel_path_str.encode("utf-8")).hexdigest()

        return thumbs_dir / f"{path_hash}.jpg"

    @Slot(str, result=str)
    def getThumbnail(self, relative_path):
        try:
            img_path = self._dataset_path / relative_path
            if not img_path.exists():
                return ""

            thumb_path = self._get_thumbnail_path(img_path)

            if not thumb_path.exists() or img_path.stat().st_mtime > thumb_path.stat().st_mtime:
                with Image.open(img_path) as img:
                    img.thumbnail((300, 300))
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    thumb_path.parent.mkdir(exist_ok=True, parents=True)
                    img.save(thumb_path, "JPEG", quality=85)

            return str(thumb_path.relative_to(self._dataset_path))
        except Exception as e:
            print(f"[Backend] Error generating thumbnail for {relative_path}: {e}")
            return ""

    @Slot()
    def cleanupThumbnails(self):
        """Scans .taggui_thumbs and deletes any orphaned thumbnail files no longer linked to dataset images."""
        try:
            thumbs_dir = self._dataset_path / ".taggui_thumbs"
            if not thumbs_dir.exists():
                return

            valid_thumbs = set()
            for img_file in self._dataset_path.rglob("*"):
                if img_file.is_file() and img_file.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                    if ".taggui_thumbs" not in img_file.parts:
                        valid_thumbs.add(self._get_thumbnail_path(img_file))

            removed_count = 0
            for thumb_file in thumbs_dir.glob("*.jpg"):
                if thumb_file not in valid_thumbs:
                    thumb_file.unlink()
                    removed_count += 1

            if removed_count > 0:
                print(f"[Backend] Garbage collection finished. Removed {removed_count} orphaned thumbnail(s).")
        except Exception as e:
            print(f"[Backend] Thumbnail cleanup error: {e}")

    @Slot(str, result=str)
    def autoTagImage(self, relative_path):
        try:
            import torch
            import timm
            import csv
            from PIL import Image
            import numpy as np
            from huggingface_hub import hf_hub_download

            img_path = self._dataset_path / relative_path
            if not img_path.exists():
                return ""

            # Load user thresholds from settings.json (defaults to 0.35 / 0.85)
            general_threshold = 0.35
            character_threshold = 0.85
            settings_path = self._dataset_path / "settings.json"
            if settings_path.exists():
                try:
                    s_data = json.loads(settings_path.read_text(encoding="utf-8"))
                    general_threshold = float(s_data.get("general_threshold", 0.35))
                    character_threshold = float(s_data.get("character_threshold", 0.85))
                except Exception:
                    pass

            # Lazy-load model and tag list into memory if not already loaded
            if not hasattr(self, "_tagger_model"):
                print("[Backend] Loading local WD-EVA02-Large Tagger v3 model...")
                model_name = "hf-hub:SmilingWolf/wd-eva02-large-tagger-v3"
                self._tagger_model = timm.create_model(model_name, pretrained=True).eval()

                self._tagger_device = "cuda" if torch.cuda.is_available() else "cpu"
                self._tagger_model.to(self._tagger_device)

                csv_path = hf_hub_download("SmilingWolf/wd-eva02-large-tagger-v3", "selected_tags.csv")

                self._tagger_labels = []
                self._tagger_categories = []
                with open(csv_path, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        self._tagger_labels.append(row["name"])
                        self._tagger_categories.append(int(row["category"]))

                print("[Backend] Local tagger model loaded successfully!")

            with Image.open(img_path) as img:
                img = img.convert("RGB")
                size = 448
                target_size = (size, size)
                img.thumbnail(target_size, Image.Resampling.LANCZOS)
                new_img = Image.new("RGB", target_size, (255, 255, 255))
                new_img.paste(img, ((size - img.width) // 2, (size - img.height) // 2))

                img_array = np.array(new_img, dtype=np.float32) / 255.0
                tensor = torch.from_numpy(img_array).permute(2, 0, 1).unsqueeze(0).to(self._tagger_device)

            with torch.no_grad():
                preds = torch.sigmoid(self._tagger_model(tensor)[0]).cpu().numpy()

            extracted_tags = []
            for idx, score in enumerate(preds):
                if idx < len(self._tagger_labels):
                    tag_name = self._tagger_labels[idx]
                    category = self._tagger_categories[idx]

                    if category == 4 and score >= character_threshold:
                        extracted_tags.append(tag_name.replace("_", " "))
                    elif category == 0 and score >= general_threshold:
                        extracted_tags.append(tag_name.replace("_", " "))

            tags_str = ", ".join(extracted_tags)

            if tags_str:
                txt_path = img_path.with_suffix(".txt")
                txt_path.write_text(tags_str, encoding="utf-8")
                print(
                    f"[Backend] Locally auto-tagged {img_path.name} (Gen: {general_threshold}, Char: {character_threshold}): {tags_str}")
                return tags_str
            else:
                print(f"[Backend] No tags crossed the threshold for {img_path.name}")
                return ""

        except Exception as e:
            print(f"[Backend] Local auto-tagging failed: {e}")
            return ""

    @Slot(str)
    def openExternalUrl(self, url_str):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url_str))