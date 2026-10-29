import json
from pathlib import Path
from PIL import Image
from PySide6.QtCore import QObject, Slot, Signal, Property
from PySide6.QtWidgets import QFileDialog


class TagGUIBridge(QObject):
    pathChanged = Signal(str)

    def __init__(self, dataset_path=None):
        super().__init__()

        # Check global config or local fallback for the last opened dataset path
        initial_path = dataset_path
        if not initial_path:
            # Look for a global config or check default settings
            default_settings = Path.cwd() / "sample_dataset" / "settings.json"
            # Alternatively, check a app-level config file for last path
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
        return json.dumps({"keywords": ""})

    @Slot(str)
    def saveDatasetSettings(self, keywords_str):
        settings_path = self._dataset_path / "settings.json"
        try:
            data = {"keywords": keywords_str}
            settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[Backend] Failed to write settings.json: {e}")

    def _scan_images(self):
        # (Keep your existing _scan_images implementation unchanged)
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

                thumb_filename = f"{f.stem}_{abs(hash(str(f)))}.webp"
                thumb_path = self.thumbs_dir / thumb_filename

                if not thumb_path.exists() or thumb_path.stat().st_mtime < f.stat().st_mtime:
                    try:
                        with Image.open(f) as img:
                            img.thumbnail((200, 200))
                            img.save(thumb_path, "WEBP", quality=85)
                    except Exception as e:
                        print(f"[Backend] Thumbnail generation failed for {f.name}: {e}")
                        thumb_path = f

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

            # Create hidden backup folder for undo restoration
            backup_dir = self._dataset_path / ".taggui_backup"
            backup_dir.mkdir(exist_ok=True)

            # Move image and txt to backup dir instead of permanent loss
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
