import json
from pathlib import Path
from PIL import Image
from PySide6.QtCore import QObject, Slot, Signal, Property
from PySide6.QtWidgets import QFileDialog
import hashlib
from huggingface_hub.constants import HF_HUB_CACHE


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
        # Default settings including model selection and thresholds for local auto-tagging
        return json.dumps({
            "keywords": "",
            "model_name": "SmilingWolf/wd-eva02-large-tagger-v3",
            "general_threshold": 0.35,
            "character_threshold": 0.85,
            "tag_strategy": "add",
            "task_command": "<CAPTION>"
        })

    @Slot(str)
    def saveDatasetSettings(self, settings_json_str):
        settings_path = self._dataset_path / "settings.json"
        try:
            if settings_path.exists():
                existing = json.loads(settings_path.read_text(encoding="utf-8"))
            else:
                existing = {}

            if settings_json_str.strip().startswith("{"):
                data = json.loads(settings_json_str)
                existing.update(data)
            else:
                existing["keywords"] = settings_json_str

            settings_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            print("[Backend] Dataset settings saved successfully.")
        except Exception as e:
            print(f"[Backend] Failed to write settings.json: {e}")

    def _is_hf_model_downloaded(self, repo_id: str) -> bool:
        try:
            folder_name = f"models--{repo_id.replace('/', '--')}"
            model_dir = Path(HF_HUB_CACHE) / folder_name
            if model_dir.exists():
                snapshots_dir = model_dir / "snapshots"
                if snapshots_dir.exists() and any(snapshots_dir.iterdir()):
                    return True
        except Exception:
            pass
        return False

    @Slot(result=str)
    def getAvailableInterrogators(self):
        wd_taggers = [
            ("SmilingWolf/wd-v1-4-convnext-tagger", 0.35),
            ("SmilingWolf/wd-v1-4-convnext-tagger-v2", 0.35),
            ("SmilingWolf/wd-v1-4-convnextv2-tagger-v2", 0.35),
            ("SmilingWolf/wd-v1-4-swinv2-tagger-v2", 0.35),
            ("SmilingWolf/wd-v1-4-vit-tagger", 0.35),
            ("SmilingWolf/wd-v1-4-vit-tagger-v2", 0.35),
            ("SmilingWolf/wd-v1-4-moat-tagger-v2", 0.35),
            ("SmilingWolf/wd-vit-tagger-v3", 0.25),
            ("SmilingWolf/wd-swinv2-tagger-v3", 0.25),
            ("SmilingWolf/wd-convnext-tagger-v3", 0.25),
            ("SmilingWolf/wd-vit-large-tagger-v3", 0.26),
            ("SmilingWolf/wd-eva02-large-tagger-v3", 0.52),
        ]

        blip2_names = [
            "Salesforce/blip2-opt-2.7b",
            "Salesforce/blip2-opt-2.7b-coco",
            "Salesforce/blip2-opt-6.7b",
            "Salesforce/blip2-opt-6.7b-coco",
            "Salesforce/blip2-flan-t5-xl",
            "Salesforce/blip2-flan-t5-xl-coco",
            "Salesforce/blip2-flan-t5-xxl",
        ]

        florence2_names = [
            "microsoft/Florence-2-base-ft",
            "microsoft/Florence-2-base",
            "microsoft/Florence-2-large-ft",
            "microsoft/Florence-2-large",
            "thwri/CogFlorence-2.2-Large",
            "MiaoshouAI/Florence-2-large-PromptGen-v2.0",
            "MiaoshouAI/Florence-2-base-PromptGen-v2.0",
        ]

        moondream2_names = ["vikhyatk/moondream2"]

        joycaption_names = [
            "fancyfeast/llama-joycaption-alpha-two-hf-llava",
            "fancyfeast/llama-joycaption-beta-one-hf-llava",
            "NeoChen1024/llama-joycaption-beta-one-hf-llava-FP8-Dynamic"
        ]

        results = []
        for name, thresh in wd_taggers:
            installed = self._is_hf_model_downloaded(name)
            results.append({
                "id": name,
                "name": f"{'[Installed] ' if installed else ''}{name}",
                "category": "tagger",
                "family": "SmilingWolf WD Tagger",
                "default_threshold": thresh,
                "installed": installed
            })

        for name in blip2_names:
            installed = self._is_hf_model_downloaded(name)
            results.append({
                "id": name,
                "name": f"{'[Installed] ' if installed else ''}{name}",
                "category": "captioner",
                "family": "BLIP-2",
                "installed": installed
            })

        for name in florence2_names:
            installed = self._is_hf_model_downloaded(name)
            commands = ["<GENERATE_TAGS>", "<CAPTION>", "<DETAILED_CAPTION>", "<MORE_DETAILED_CAPTION>", "<ANALYZE>"] if "PromptGen" in name else ["<CAPTION>", "<DETAILED_CAPTION>", "<MORE_DETAILED_CAPTION>", "<CAPTION_TO_PHRASE_GROUNDING>", "<OD>"]
            results.append({
                "id": name,
                "name": f"{'[Installed] ' if installed else ''}{name}",
                "category": "florence2",
                "family": "Florence-2",
                "commands": commands,
                "installed": installed
            })

        for name in moondream2_names:
            installed = self._is_hf_model_downloaded(name)
            results.append({
                "id": name,
                "name": f"{'[Installed] ' if installed else ''}{name}",
                "category": "moondream",
                "family": "Moondream2",
                "commands": ["Short_caption", "Normal_caption", "Visual_query", "Object_detection", "Pointing"],
                "installed": installed
            })

        for name in joycaption_names:
            installed = self._is_hf_model_downloaded(name)
            results.append({
                "id": name,
                "name": f"{'[Installed] ' if installed else ''}{name}",
                "category": "captioner",
                "family": "JoyCaption",
                "installed": installed
            })

        return json.dumps(results)

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
    def autoTagBatch(self, paths_json_str):
        """Processes a batch of images with a single model load, logs live progress, then automatically unloads and frees VRAM."""
        try:
            import torch
            from PIL import Image
            import json
            import gc

            paths = json.loads(paths_json_str)
            if not paths:
                return json.dumps({})

            general_threshold = 0.35
            character_threshold = 0.85
            model_name = "SmilingWolf/wd-eva02-large-tagger-v3"
            task_command = "<CAPTION>"

            settings_path = self._dataset_path / "settings.json"
            if settings_path.exists():
                try:
                    s_data = json.loads(settings_path.read_text(encoding="utf-8"))
                    general_threshold = float(s_data.get("general_threshold", 0.35))
                    character_threshold = float(s_data.get("character_threshold", 0.85))
                    model_name = s_data.get("model_name", "SmilingWolf/wd-eva02-large-tagger-v3")
                    task_command = s_data.get("task_command", "<CAPTION>")
                except Exception:
                    pass

            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if device == "cuda" else torch.float32

            results = {}
            is_vlm = any(k in model_name.lower() for k in ["blip2", "florence", "moondream", "joycaption", "qwen"])

            model = None
            processor = None
            tagger_model = None
            tagger_labels = []
            tagger_categories = []

            # 1. Load model ONCE before entering the batch loop
            if is_vlm:
                from transformers import AutoProcessor
                print(f"[Backend] Loading captioning model for batch: {model_name}...")
                processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)

                if "blip2" in model_name.lower():
                    from transformers import Blip2ForConditionalGeneration
                    model = Blip2ForConditionalGeneration.from_pretrained(model_name, torch_dtype=dtype,
                                                                          trust_remote_code=True).to(device)
                elif "florence" in model_name.lower():
                    from transformers import AutoModelForImageTextToText
                    model = AutoModelForImageTextToText.from_pretrained(model_name, torch_dtype=dtype,
                                                                        trust_remote_code=True).to(device)
                elif "moondream" in model_name.lower():
                    from transformers import AutoModelForCausalLM
                    model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True,
                                                                 revision="2024-05-08", torch_dtype=dtype).to(device)
                else:
                    try:
                        from transformers import AutoModelForVision2Seq
                        model = AutoModelForVision2Seq.from_pretrained(model_name, torch_dtype=dtype,
                                                                       trust_remote_code=True).to(device)
                    except ImportError:
                        from transformers import AutoModelForCausalLM
                        model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=dtype,
                                                                     trust_remote_code=True).to(device)
            else:
                import timm
                import csv
                from huggingface_hub import hf_hub_download
                print(f"[Backend] Loading tagger model for batch: {model_name}...")
                hf_model_str = f"hf-hub:{model_name}"
                tagger_model = timm.create_model(hf_model_str, pretrained=True).eval().to(device)
                csv_path = hf_hub_download(model_name, "selected_tags.csv")
                with open(csv_path, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        tagger_labels.append(row["name"])
                        tagger_categories.append(int(row["category"]))

            # 2. Loop through all images in the batch efficiently
            for i, rel_path in enumerate(paths):
                img_path = self._dataset_path / rel_path
                if not img_path.exists():
                    continue

                try:
                    if is_vlm:
                        with Image.open(img_path) as img:
                            image = img.convert("RGB")
                        generated_text = ""
                        with torch.no_grad():
                            if "florence" in model_name.lower():
                                prompt = task_command if task_command else "<CAPTION>"
                                inputs = processor(text=prompt, images=image, return_tensors="pt").to(device, dtype)
                                generated_ids = model.generate(input_ids=inputs["input_ids"],
                                                               pixel_values=inputs["pixel_values"], max_new_tokens=1024,
                                                               num_beams=3)
                                generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
                                generated_text = \
                                processor.post_process_generation(generated_text, task=prompt, image_size=image.size)[
                                    prompt]
                            elif "moondream" in model_name.lower():
                                enc_image = model.encode_image(image)
                                generated_text = model.answer_question(enc_image, "Describe this image concisely.",
                                                                       processor)
                            else:
                                inputs = processor(images=image, return_tensors="pt").to(device, dtype)
                                generated_ids = model.generate(**inputs, max_new_tokens=100)
                                generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[
                                    0].strip()
                        tags_str = generated_text
                    else:
                        import numpy as np
                        with Image.open(img_path) as img:
                            img = img.convert("RGB")
                            size = 448
                            target_size = (size, size)
                            img.thumbnail(target_size, Image.Resampling.LANCZOS)
                            new_img = Image.new("RGB", target_size, (255, 255, 255))
                            new_img.paste(img, ((size - img.width) // 2, (size - img.height) // 2))

                            img_array = np.array(new_img, dtype=np.float32) / 255.0
                            tensor = torch.from_numpy(img_array).permute(2, 0, 1).unsqueeze(0).to(device)

                        with torch.no_grad():
                            preds = torch.sigmoid(tagger_model(tensor)[0]).cpu().numpy()

                        extracted_tags = []
                        for idx, score in enumerate(preds):
                            if idx < len(tagger_labels):
                                tag_name = tagger_labels[idx]
                                category = tagger_categories[idx]
                                if category == 4 and score >= character_threshold:
                                    extracted_tags.append(tag_name.replace("_", " "))
                                elif category == 0 and score >= general_threshold:
                                    extracted_tags.append(tag_name.replace("_", " "))
                        tags_str = ", ".join(extracted_tags)

                    if tags_str:
                        txt_path = img_path.with_suffix(".txt")
                        txt_path.write_text(tags_str, encoding="utf-8")
                        results[rel_path] = tags_str
                        # Live console log showing progress and result for each picture
                        print(
                            f"[Backend] ({i + 1}/{len(paths)}) Processed {img_path.name} using {model_name}: {tags_str}")
                except Exception as img_err:
                    print(f"[Backend] Error processing {rel_path}: {img_err}")

            # 3. Automatically UNLOAD model and clear VRAM immediately after batch completes
            if model is not None:
                del model
            if processor is not None:
                del processor
            if tagger_model is not None:
                del tagger_model

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("[Backend] Batch processing finished. VRAM successfully cleared.")

            return json.dumps(results)

        except Exception as e:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print(f"[Backend] Batch processing failed: {e}")
            import traceback
            traceback.print_exc()
            return json.dumps({})

    @Slot()
    def unloadActiveModel(self):
        """Explicitly clear heavy models from VRAM when done batching."""
        import gc
        import torch
        if hasattr(self, "_caption_model"):
            del self._caption_model
            del self._caption_processor
            del self._loaded_caption_model_name
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("[Backend] VRAM model cache cleared.")

    @Slot(str)
    def openExternalUrl(self, url_str):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url_str))