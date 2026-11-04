import os
import json
import gc
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import numpy as np
import torch

from PySide6.QtCore import QObject, Slot, Signal, Property, QThread, QEventLoop, Qt
from PySide6.QtWidgets import QFileDialog, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QFrame
from PySide6.QtGui import QIcon, QColor
from huggingface_hub.constants import HF_HUB_CACHE

from autotagger import AutoTagWorker
from backend import DeleteConfirmDialog, TaggingConfirmDialog, TaggingProgressDialog, SettingsDialog, PromptInputDialog, KeywordGroupsDialog

# version = 1.2.25

# ==============================================================================
#  DEBUG CONFIGURATION
# ==============================================================================
DEBUG_MODE = False  # Set to True for verbose logs, False for clean logs

# ==============================================================================
# MAIN BRIDGE CLASS
# ==============================================================================

class TagGUIBridge(QObject):
    pathChanged = Signal(str)

    def __init__(self, dataset_path=None, parent_window=None):
        super().__init__()
        self.parent_window = parent_window

        initial_path = dataset_path
        if not initial_path:
            config_path = Path.cwd() / "assets/settings.json"
            if config_path.exists():
                try:
                    config_data = json.loads(config_path.read_text(encoding="utf-8"))
                    saved_path = Path(config_data.get("last_path", ""))
                    if saved_path.exists():
                        initial_path = saved_path
                except Exception as e:
                    print(f"[Backend] Failed to load settings.json: {e}")

        self._dataset_path = (
            Path(initial_path) if initial_path else Path.cwd() / "sample_dataset"
        )
        self._dataset_path.mkdir(exist_ok=True)

        self.thumbs_dir = self._dataset_path / ".taggui_thumbs"
        self.thumbs_dir.mkdir(exist_ok=True)

        self._save_last_path_config()
        self.cleanupThumbnails()
        self._e621_tag_index = []

    def _load_e621_csv(self):
        try:
            possible_paths = [
                Path.cwd() / "assets" / "tags" / "e621.csv",
                Path.cwd() / "assets" / "tags" / "e621_sample.csv",
                Path.cwd() / "assets" / "e621.csv",
                Path.cwd() / "assets" / "e621_sample.csv",
                Path.cwd() / "e621_sample.csv"
            ]
            csv_path = next((p for p in possible_paths if p.exists()), None)

            if csv_path:
                import csv
                with open(csv_path, mode="r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if not row:
                            continue
                        main_tag = row[0].strip().lower()
                        aliases = []
                        if len(row) >= 4:
                            aliases = [a.strip().lower() for a in row[3].split(",") if a.strip()]

                        self._e621_tag_index.append({
                            "main": main_tag,
                            "aliases": aliases
                        })
        except Exception as e:
            print(f"[Backend Warning] Failed to load e621 CSV: {e}")

    @Slot(str, result=str)
    def getE621AutocompleteSuggestions(self, query):
        settings = json.loads(self.getDatasetSettings())
        if not settings.get("use_e621", False) or not query.strip():
            return json.dumps([])

        if not self._e621_tag_index:
            self._load_e621_csv()

        q = query.strip().lower()
        matches = []
        seen = set()

        for entry in self._e621_tag_index:
            if q in entry["main"] or any(q in alias for alias in entry["aliases"]):
                if entry["main"] not in seen:
                    seen.add(entry["main"])
                    matches.append(entry["main"])
                for alias in entry["aliases"]:
                    if q in alias and alias not in seen:
                        seen.add(alias)
                        matches.append(alias)
                if len(matches) >= 10:
                    break

        return json.dumps(matches[:8])

    @Slot(result=bool)
    def isE621Enabled(self):
        settings = json.loads(self.getDatasetSettings())
        return settings.get("use_e621", False)

    def _save_last_path_config(self):
        try:
            config_path = Path.cwd() / "assets/settings.json"
            config_path.write_text(
                json.dumps({"last_path": str(self._dataset_path.resolve())}, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"[Backend] Failed to save settings.json: {e}")

    @Property(str, notify=pathChanged)
    def dataset_path_str(self):
        return str(self._dataset_path.resolve())

    @Slot(result=str)
    def browseDatasetFolder(self):
        initial_dir = str(self._dataset_path) if self._dataset_path.exists() else str(Path.cwd())

        folder_path = QFileDialog.getExistingDirectory(
            self.parent_window,
            "Select Dataset Folder",
            initial_dir
        )

        if folder_path:
            self._dataset_path = Path(folder_path)
            self._dataset_path.mkdir(exist_ok=True)

            self.thumbs_dir = self._dataset_path / ".taggui_thumbs"
            self.thumbs_dir.mkdir(exist_ok=True)
            self._save_last_path_config()

            self.pathChanged.emit(str(self._dataset_path))

            if hasattr(self, 'getDatasetImages'):
                return self.getDatasetImages()

        return ""

    @Slot(result=str)
    def getDatasetSettings(self):
        default_settings = {
            "keywords": "",
            "keyword_groups": {
                "general": ["masterpiece", "best quality"],
                "characters": ["1girl", "solo"]
            },
            "use_e621": False,
            "model_name": "SmilingWolf/wd-eva02-large-tagger-v3",
            "general_threshold": 0.35,
            "character_threshold": 0.85,
            "general_mcut_enabled": False,
            "character_mcut_enabled": False,
            "tag_strategy": "add",
            "task_command": "<CAPTION>",
            "custom_commands": [],
            "thinking_mode": False,
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 20,
            "qwen_max_new_tokens": 256,
            "qwen_min_new_tokens": 10,
            "captioner_max_new_tokens": 150,
            "captioner_min_length": 30,
            "captioner_do_sample": True,
            "captioner_temperature": 0.7,
            "captioner_repetition_penalty": 1.2,
            "captioner_num_beams": 3
        }

        settings_path = self._dataset_path / "settings.json"
        if settings_path.exists():
            try:
                content = settings_path.read_text(encoding="utf-8")
                json.loads(content)
                return content
            except json.JSONDecodeError as jde:
                print(f"[Backend Warning] settings.json corrupt: {jde}. Falling back to defaults.")
            except Exception as e:
                print(f"[Backend Warning] Failed to read settings.json: {e}. Falling back to defaults.")

        return json.dumps(default_settings, indent=2)

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
            if DEBUG_MODE:
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

        blip_names = [
            "Salesforce/blip-image-captioning-large",           # Extremely lightweight, fast, and stable. Uses a ViT-large vision backbone. It outputs concise, accurate, and clean natural-language sentences.
            "unography/blip-long-cap",                          # Fine-tuned specifically to output longer, more descriptive paragraphs rather than short single-sentence descriptions
            "ifmain/blip-image2promt-stable-diffusion-base"     # Specialized fine-tune designed to output comma-separated tags or prompt tokens useful for Stable Diffusion generation rather than strict descriptive prose
        ]

        blip2_names = [
            "Salesforce/blip2-opt-2.7b",
            "Salesforce/blip2-opt-2.7b-coco",       # fine-tuned specifically on COCO dataset styles
            "Salesforce/blip2-opt-6.7b",
            "Salesforce/blip2-opt-6.7b-coco",       # fine-tuned specifically on COCO dataset styles
            "Salesforce/blip2-flan-t5-xl",          # (~3B total parameters) instruction-tuned model
            "Salesforce/blip2-flan-t5-xl-coco",     # fine-tuned specifically on COCO dataset styles
            "Salesforce/blip2-flan-t5-xxl",         # (~11B parameters) instruction-tuned model, making these variants substantially better at following structured text commands (e.g., answering questions or adhering to specific prompt formats).
        ]

        joycaption_names = [
            # "fancyfeast/llama-joycaption-alpha-two-hf-llava",
            # "fancyfeast/llama-joycaption-beta-one-hf-llava",
            # "NeoChen1024/llama-joycaption-beta-one-hf-llava-FP8-Dynamic",
            # "NeoChen1024/llama-joycaption-beta-one-hf-llava-GPTQ-4bit-sym-autoround",
            # "mradermacher/llama-joycaption-beta-one-hf-llava-GGUF"
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

        qwen_names = [
            "Qwen/Qwen3-VL-4B-Instruct",
            "DreamFast/Qwen3-VL-4b-Heretic",
        ]

        minicpm_names = [
            "openbmb/MiniCPM-V-2_6-int4",
        ]

        results = []
        for name, thresh in wd_taggers:
            installed = self._is_hf_model_downloaded(name)
            results.append({
                "id": name,
                # "name": f"{'[Installed] ' if installed else ''}{name}",
                "name": name,
                "category": "tagger",
                "family": "SmilingWolf WD Tagger",
                "default_threshold": thresh,
                "installed": installed
            })

        for name in blip_names:
            installed = self._is_hf_model_downloaded(name)
            blip_commands = [
                "A detailed, descriptive caption of this image with background details:",
                "A concise caption of this image:",
                "A photo of"
            ]
            results.append({
                "id": name,
                # "name": f"{'[Installed] ' if installed else ''}{name}",
                "name": name,
                "category": "captioner",
                "family": "BLIP",
                "commands": blip_commands,
                "installed": installed
            })

        for name in blip2_names:
            installed = self._is_hf_model_downloaded(name)
            blip2_commands = [
                "Write a detailed caption for this image.",
                "Describe this image concisely.",
                "A detailed photograph of"
            ]
            results.append({
                "id": name,
                # "name": f"{'[Installed] ' if installed else ''}{name}",
                "name": name,
                "category": "captioner",
                "family": "BLIP-2",
                "commands": blip2_commands,
                "installed": installed
            })

        for name in florence2_names:
            installed = self._is_hf_model_downloaded(name)
            commands = ["<GENERATE_TAGS>", "<CAPTION>", "<DETAILED_CAPTION>", "<MORE_DETAILED_CAPTION>",
                        "<ANALYZE>"] if "PromptGen" in name else ["<CAPTION>", "<DETAILED_CAPTION>",
                                                                  "<MORE_DETAILED_CAPTION>"]
            results.append({
                "id": name,
                # "name": f"{'[Installed] ' if installed else ''}{name}",
                "name": name,
                "category": "florence2",
                "family": "Florence-2",
                "commands": commands,
                "installed": installed
            })

        for name in moondream2_names:
            installed = self._is_hf_model_downloaded(name)
            results.append({
                "id": name,
                # "name": f"{'[Installed] ' if installed else ''}{name}",
                "name": name,
                "category": "moondream",
                "family": "Moondream2",
                "commands": ["Short_caption", "Normal_caption", "Visual_query", "Object_detection", "Pointing"],
                "installed": installed
            })

        for name in qwen_names:
            installed = self._is_hf_model_downloaded(name)
            commands = [
                "Describe this image concisely.",
                "Describe this image in detail",
                "Write a detailed caption for this image.",
                "List all visible tags and keywords in this image."
            ]
            results.append({
                "id": name,
                # "name": f"{'[Installed] ' if installed else ''}{name}",
                "name": name,
                "category": "qwen",
                "family": "Qwen-VL",
                "commands": commands,
                "installed": installed
            })

        for name in joycaption_names:
            installed = self._is_hf_model_downloaded(name)
            joycaption_commands = [
                "Write a descriptive caption for this image.",
                "Write a detailed booru-style tag list and caption.",
                "Describe this image focusing on character details."
            ]
            results.append({
                "id": name,
                # "name": f"{'[Installed] ' if installed else ''}{name}",
                "name": name,
                "category": "captioner",
                "family": "JoyCaption",
                "commands": joycaption_commands,
                "installed": installed
            })

        for name in minicpm_names:
            installed = self._is_hf_model_downloaded(name)
            minicpm_commands = [
                "What is in the image?",
            ]
            results.append({
                "id": name,
                "name": name,
                "category": "minicpm",
                "family": "MiniCPM ",
                "commands": minicpm_commands,
                "installed": installed
            })

        return json.dumps(results)

    @Slot(str, str)
    def saveImageTags(self, relative_path, tags_comma_separated):
        txt_path = self._dataset_path / Path(relative_path).with_suffix(".txt")
        cleaned_tags = tags_comma_separated.strip()

        if not cleaned_tags:
            # If tags are empty, remove the text file if it exists so we don't keep empty files
            if txt_path.exists():
                txt_path.unlink()
        else:
            txt_path.write_text(cleaned_tags, encoding="utf-8")

    @Slot(str)
    def saveBatchImageTags(self, updates_json_str):
        try:
            updates = json.loads(updates_json_str)
            for rel_path, tags_str in updates.items():
                txt_path = self._dataset_path / Path(rel_path).with_suffix(".txt")
                cleaned_tags = tags_str.strip()

                if not cleaned_tags:
                    if txt_path.exists():
                        txt_path.unlink()
                else:
                    txt_path.write_text(cleaned_tags, encoding="utf-8")
        except Exception as e:
            print(f"[Backend] Batch save failed: {e}")

    @Slot(str, result=int)
    def estimateTokens(self, tags_string):
        if not tags_string:
            return 0
        if "," not in tags_string and " " in tags_string:
            words = [w.strip() for w in tags_string.split() if w.strip()]
            return int(len(words) * 1.3)
        tokens = [t.strip() for t in tags_string.split(",") if t.strip()]
        return int(len(tokens) * 1.5)

    @Slot(str, result=bool)
    def confirmAutoTagModal(self, count):
        settings = json.loads(self.getDatasetSettings())
        model_name = settings.get("model_name", "selected model")
        dialog = TaggingConfirmDialog(count, model_name=model_name, parent=self.parent_window)
        return dialog.exec() == QDialog.Accepted

    @Slot(str, result=bool)
    def confirmDeleteModal(self, filename):
        dialog = DeleteConfirmDialog(filename, parent=self.parent_window)
        return dialog.exec() == QDialog.Accepted

    @Slot(str)
    def deleteImageAndTags(self, relative_path):
        try:
            import shutil
            trash_dir = self._dataset_path / ".taggui_trash"
            trash_dir.mkdir(parents=True, exist_ok=True)

            img_path = self._dataset_path / relative_path
            txt_path = img_path.with_suffix(".txt")

            dest_img_path = trash_dir / relative_path
            dest_img_path.parent.mkdir(parents=True, exist_ok=True)
            dest_txt_path = dest_img_path.with_suffix(".txt")

            if img_path.exists():
                shutil.move(str(img_path), str(dest_img_path))
            if txt_path.exists():
                shutil.move(str(txt_path), str(dest_txt_path))

            thumb_dir = self._dataset_path / ".taggui_thumbs"
            if thumb_dir.exists():
                thumb_filename = f"tn_{img_path.name}"
                thumb_path = img_path.parent / thumb_filename
                absolute_thumb = thumb_dir / thumb_path.relative_to(self._dataset_path)
                if absolute_thumb.exists():
                    absolute_thumb.unlink()

            print(f"[Backend] Moved image and tags to local dataset trash: {relative_path}")
        except Exception as e:
            print(f"[Backend] Failed to move files to local trash: {e}")

    @Slot(str)
    def restoreImageAndTags(self, relative_path):
        try:
            import shutil
            trash_dir = self._dataset_path / ".taggui_trash"
            if not trash_dir.exists():
                return

            trash_img_path = trash_dir / relative_path
            trash_txt_path = trash_img_path.with_suffix(".txt")

            target_img_path = self._dataset_path / relative_path
            target_txt_path = target_img_path.with_suffix(".txt")
            target_img_path.parent.mkdir(parents=True, exist_ok=True)

            if trash_img_path.exists():
                shutil.move(str(trash_img_path), str(target_img_path))
            if trash_txt_path.exists():
                shutil.move(str(trash_txt_path), str(target_txt_path))

            print(f"[Backend] Successfully restored {relative_path} from local dataset trash.")
        except Exception as e:
            print(f"[Backend] Failed to restore image from local trash: {e}")

    @Slot(result=str)
    def getDatasetImages(self):
        try:
            valid_extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
            thumb_dir = self._dataset_path / ".taggui_thumbs"
            thumb_dir.mkdir(exist_ok=True)

            image_paths = []
            for path in self._dataset_path.rglob("*"):
                if path.is_file() and path.suffix.lower() in valid_extensions:
                    if ".taggui_thumbs" in path.parts or ".taggui_trash" in path.parts:
                        continue
                    image_paths.append(path)

            def process_image(path):
                rel_path = path.relative_to(self._dataset_path).as_posix()
                thumb_filename = f"tn_{path.name}"
                thumb_path = path.parent / thumb_filename
                absolute_thumb_path = thumb_dir / thumb_path.relative_to(self._dataset_path)
                absolute_thumb_path.parent.mkdir(parents=True, exist_ok=True)

                if not absolute_thumb_path.exists() or path.stat().st_mtime > absolute_thumb_path.stat().st_mtime:
                    try:
                        with Image.open(path) as img:
                            img.thumbnail((300, 300))
                            img.save(absolute_thumb_path, quality=85)
                    except Exception as thumb_err:
                        print(f"[Backend] Thumbnail generation failed for {rel_path}: {thumb_err}")

                txt_path = path.with_suffix(".txt")
                tags = []
                if txt_path.exists():
                    try:
                        content = txt_path.read_text(encoding="utf-8")
                        tags = [t.strip() for t in content.replace("\n", ",").split(",") if t.strip()]
                    except Exception:
                        pass

                image_entry = {
                    "filename": path.name,
                    "relative_path": rel_path,
                    "url": absolute_thumb_path.as_uri(),
                    "tags": tags
                }
                return image_entry, rel_path

            images = []
            current_rel_paths = set()
            max_threads = min(32, (os.cpu_count() or 4) * 2)

            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                results = list(executor.map(process_image, image_paths))

            for img_dict, rel_path in results:
                images.append(img_dict)
                current_rel_paths.add(rel_path)

            if thumb_dir.exists():
                thumb_files = [f for f in thumb_dir.rglob("*") if f.is_file()]

                def prune_thumb(thumb_file):
                    try:
                        rel_thumb = thumb_file.relative_to(thumb_dir)
                        original_rel_parts = list(rel_thumb.parts)
                        if original_rel_parts:
                            original_rel_parts[-1] = original_rel_parts[-1][3:] if original_rel_parts[-1].startswith("tn_") else original_rel_parts[-1]
                            original_rel_path = "/".join(original_rel_parts)
                            if original_rel_path not in current_rel_paths:
                                thumb_file.unlink()
                                print(f"[Backend] Pruned orphaned thumbnail: {thumb_file.name}")
                    except Exception:
                        pass

                with ThreadPoolExecutor(max_workers=4) as prune_executor:
                    prune_executor.map(prune_thumb, thumb_files)

            return json.dumps(images)

        except Exception as e:
            print(f"[Backend] Failed to load dataset images: {e}")
            return json.dumps([])

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

    @Slot()
    def cleanupThumbnails(self):
        try:
            thumbs_dir = self._dataset_path / ".taggui_thumbs"
            if not thumbs_dir.exists():
                return

            valid_thumbs = set()
            for img_file in self._dataset_path.rglob("*"):
                if img_file.is_file() and img_file.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
                    if ".taggui_thumbs" in img_file.parts or ".taggui_trash" in img_file.parts:
                        continue
                    thumb_filename = f"tn_{img_file.name}"
                    thumb_path = img_file.parent / thumb_filename
                    absolute_thumb = thumbs_dir / thumb_path.relative_to(self._dataset_path)
                    valid_thumbs.add(absolute_thumb)

            removed_count = 0
            for thumb_file in thumbs_dir.rglob("*"):
                if thumb_file.is_file():
                    if thumb_file not in valid_thumbs:
                        try:
                            thumb_file.unlink()
                            removed_count += 1
                        except Exception:
                            pass

            if removed_count > 0:
                print(f"[Backend] Garbage collection finished. Removed {removed_count} orphaned thumbnail(s).")
        except Exception as e:
            print(f"[Backend] Thumbnail cleanup error: {e}")

    def _mcut_threshold(self, probs):
        sorted_probs = np.sort(probs)[::-1]
        diffs = sorted_probs[:-1] - sorted_probs[1:]
        if len(diffs) == 0:
            return 0.35
        index = np.argmax(diffs)
        return float(sorted_probs[index + 1])

    @Slot(str, result=str)
    def autoTagBatch(self, paths_json_str):
        try:
            paths = json.loads(paths_json_str)
            if not paths:
                return json.dumps({})

            settings = json.loads(self.getDatasetSettings())
            self.worker = AutoTagWorker(self, paths, settings)

            progress_dialog = TaggingProgressDialog(worker_ref=self.worker, parent=self.parent_window)
            progress_dialog.show()

            self.worker.log_signal.connect(progress_dialog.append_log)

            loop = QEventLoop()
            final_json_results = "{}"

            def handle_finished(results_str):
                nonlocal final_json_results
                final_json_results = results_str
                progress_dialog.tagging_finished()

            self.worker.finished_signal.connect(handle_finished)
            self.worker.finished_signal.connect(self.worker.deleteLater)

            progress_dialog.accepted.connect(loop.quit)

            self.worker.start()
            loop.exec()

            return final_json_results

        except Exception as e:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print(f"[Backend] Failed: {e}")
            import traceback
            traceback.print_exc()
            return json.dumps("{}")

    @Slot()
    def unloadActiveModel(self):
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

    @Slot(dict)
    def updateSettings(self, settings_dict):
        try:
            settings_path = self._dataset_path / "settings.json"
            existing = {}
            if settings_path.exists():
                existing = json.loads(settings_path.read_text(encoding="utf-8"))

            existing.update(settings_dict)
            settings_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            if DEBUG_MODE:
                print(f"[Backend] Updated and saved generation settings -> {settings_dict}")
        except Exception as e:
            print(f"[Backend] Failed to update settings in bridge: {e}")

    @Slot()
    def openNativeSettingsDialog(self):
        try:
            settings_json = self.getDatasetSettings()
            current_settings = json.loads(settings_json)

            interrogators_json = self.getAvailableInterrogators()
            interrogators = json.loads(interrogators_json)

            dialog = SettingsDialog(current_settings, interrogators, parent=self.parent_window)
            if dialog.exec() == QDialog.Accepted:
                updated = dialog.get_updated_settings()
                self.saveDatasetSettings(json.dumps(updated))
                if DEBUG_MODE:
                    print("[Backend] Dataset settings saved successfully.")
        except Exception as e:
            print(f"[Backend] Error opening native settings dialog: {e}")

    @Slot(str, str, result=str)
    def openNativeEditPromptDialog(self, title_text, initial_value):
        try:
            # Ensure you are using your unified PromptInputDialog class
            dialog = PromptInputDialog(
                title_text=title_text,
                initial_value=initial_value,
                badge_icon="✏️",
                confirm_text="Save Changes",
                parent=self.parent_window
            )
            if dialog.exec() == QDialog.Accepted:
                return dialog.get_text() # <--- Changed from get_edited_text() to get_text()
        except Exception as e:
            print(f"[Backend] Error opening native edit prompt dialog: {e}")
        return ""

    @Slot()
    def openNativeKeywordGroupsDialog(self):
        try:
            settings_json = self.getDatasetSettings()
            current_settings = json.loads(settings_json)
            current_groups = current_settings.get("keyword_groups", {})

            dialog = KeywordGroupsDialog(current_groups, parent=self.parent_window)
            if dialog.exec() == QDialog.Accepted:
                updated_groups = dialog.get_updated_groups()
                current_settings["keyword_groups"] = updated_groups
                self.saveDatasetSettings(json.dumps(current_settings))
                if DEBUG_MODE:
                    print("[Backend] Keyword groups saved successfully.")
        except Exception as e:
            print(f"[Backend] Error opening keyword groups dialog: {e}")
