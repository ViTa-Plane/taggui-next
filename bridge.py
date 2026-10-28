import json
from pathlib import Path
from PIL import Image
from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QFileDialog


class TagGUIBridge(QObject):

    def __init__(self, dataset_path=None):
        super().__init__()
        self.dataset_path = (
            Path(dataset_path) if dataset_path else Path.cwd() / "sample_dataset"
        )
        self.dataset_path.mkdir(exist_ok=True)

        self.thumbs_dir = self.dataset_path / ".taggui_thumbs"
        self.thumbs_dir.mkdir(exist_ok=True)

    @Slot(result=str)
    def getDatasetImages(self):
        return json.dumps(self._scan_images())

    @Slot(result=str)
    def browseDatasetFolder(self):
        dir_path = QFileDialog.getExistingDirectory(None, "Select Dataset Directory")
        if dir_path:
            self.dataset_path = Path(dir_path)
            self.thumbs_dir = self.dataset_path / ".taggui_thumbs"
            self.thumbs_dir.mkdir(exist_ok=True)
            print(f"[Backend] Switched dataset path to: {self.dataset_path}")
            return json.dumps(self._scan_images())
        return ""

    def _scan_images(self):
        images = []
        valid_exts = {".png", ".jpg", ".jpeg", ".webp"}

        for f in self.dataset_path.rglob("*"):
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

                rel_path = f.relative_to(self.dataset_path)

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
        txt_path = self.dataset_path / Path(relative_path).with_suffix(".txt")
        txt_path.write_text(tags_comma_separated, encoding="utf-8")

    @Slot(str)
    def saveBatchImageTags(self, updates_json_str):
        """Batch updates multiple sidecar txt files at once."""
        try:
            updates = json.loads(updates_json_str)
            for rel_path, tags_str in updates.items():
                txt_path = self.dataset_path / Path(rel_path).with_suffix(".txt")
                txt_path.write_text(tags_str, encoding="utf-8")
        except Exception as e:
            print(f"[Backend] Batch save failed: {e}")

    @Slot(str, result=int)
    def estimateTokens(self, tags_string):
        tokens = [t.strip() for t in tags_string.split(",") if t.strip()]
        return int(len(tokens) * 1.5)