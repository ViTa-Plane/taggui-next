import os
import sys
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


# ==============================================================================
# FANCIER DARK THEME CONFIRMATION & PROGRESS DIALOGS
# ==============================================================================

class TaggingConfirmDialog(QDialog):
    def __init__(self, count, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TagGUI Next - Confirm Auto-Tag")
        self.resize(420, 200)
        self.setModal(True)

        # Make window borderless and keep transparent or dark rounded corners
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))


        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)

        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        badge = QLabel("✨")
        badge.setStyleSheet("""
            background: rgba(99, 102, 241, 0.2);
            border: 1px solid rgba(99, 102, 241, 0.4);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 14px;
        """)
        header_layout.addWidget(badge)

        title = QLabel("RUN LOCAL PYTORCH AUTOTAG")
        title.setObjectName("titleLabel")
        header_layout.addWidget(title)
        header_layout.addStretch()
        card_layout.addLayout(header_layout)

        desc = QLabel(f"Run local PyTorch auto-tagger for <b>{count}</b> selected image(s)? This will process images using your selected model configuration.")
        desc.setObjectName("descLabel")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.clicked.connect(self.reject)

        self.confirm_btn = QPushButton("Start AutoTag")
        self.confirm_btn.setObjectName("confirmBtn")
        self.confirm_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.confirm_btn)
        card_layout.addLayout(btn_layout)

        main_layout.addWidget(card)


class DeleteConfirmDialog(QDialog):
    def __init__(self, filename, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TagGUI Next - Confirm Deletion")
        self.resize(420, 200)
        self.setModal(True)

        # Make window borderless and keep transparent or dark rounded corners
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)

        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        badge = QLabel("🗑️")
        badge.setStyleSheet("""
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid rgba(239, 68, 68, 0.4);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 14px;
        """)
        header_layout.addWidget(badge)

        title = QLabel("DELETE IMAGE & TAGS")
        title.setObjectName("titleLabel")
        header_layout.addWidget(title)
        header_layout.addStretch()
        card_layout.addLayout(header_layout)

        desc = QLabel(f"Are you sure you want to delete <b>{filename}</b> and its corresponding <code>.txt</code> tags file? This moves them to the local dataset trash.")
        desc.setObjectName("descLabel")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.clicked.connect(self.reject)

        self.confirm_btn = QPushButton("Delete Files")
        self.confirm_btn.setObjectName("deleteBtn")
        self.confirm_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.confirm_btn)
        card_layout.addLayout(btn_layout)

        main_layout.addWidget(card)


class TaggingProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TagGUI Next - Auto-Tagging")
        self.resize(620, 420)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        #Make window borderless and keep transparent or dark rounded corners
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)

        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        badge = QLabel("✨")
        badge.setStyleSheet("""
            background: rgba(99, 102, 241, 0.2);
            border: 1px solid rgba(99, 102, 241, 0.4);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 14px;
        """)
        header_layout.addWidget(badge)

        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        title = QLabel("AUTOTAG BATCH PROCESS")
        title.setObjectName("titleLabel")

        self.status_label = QLabel("Initializing engine...")
        self.status_label.setObjectName("statusLabel")

        header_text.addWidget(title)
        header_text.addWidget(self.status_label)
        header_layout.addLayout(header_text)
        header_layout.addStretch()

        card_layout.addLayout(header_layout)

        self.log_output = QTextEdit()
        self.log_output.setObjectName("logOutput")
        self.log_output.setReadOnly(True)
        card_layout.addWidget(self.log_output)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        self.close_btn = QPushButton("Done")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(self.close_btn)

        card_layout.addLayout(footer_layout)
        main_layout.addWidget(card)

    def append_log(self, text: str):
        self.log_output.append(text)
        sb = self.log_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def tagging_finished(self):
        self.status_label.setText("Batch Auto-Tagging Complete!")
        self.status_label.setStyleSheet("color: #34d399; font-size: 11px; font-family: monospace; font-weight: bold;")
        self.close_btn.setEnabled(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self.show()


class AutoTagWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(str)

    def __init__(self, bridge, paths, settings):
        super().__init__()
        self.bridge = bridge
        self.paths = paths
        self.settings = settings

    def run(self):
        results = {}
        try:
            general_threshold = self.settings.get("general_threshold", 0.35)
            character_threshold = self.settings.get("character_threshold", 0.85)
            general_mcut_enabled = self.settings.get("general_mcut_enabled", False)
            character_mcut_enabled = self.settings.get("character_mcut_enabled", False)
            model_name = self.settings.get("model_name", "SmilingWolf/wd-eva02-large-tagger-v3")
            task_command = self.settings.get("task_command", "<CAPTION>")

            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if device == "cuda" else torch.float32

            is_vlm = any(k in model_name.lower() for k in ["blip", "florence", "moondream", "joycaption", "qwen"])

            model = None
            processor = None
            tagger_model = None
            tagger_labels = []
            tagger_categories = []

            if is_vlm:
                self.log_signal.emit(f"[Backend] Loading captioning/VLM model: {model_name}...")

                if "blip" in model_name.lower() and "blip2" not in model_name.lower():
                    from transformers import BlipProcessor, BlipForConditionalGeneration
                    processor = BlipProcessor.from_pretrained(model_name, trust_remote_code=True)
                    model = BlipForConditionalGeneration.from_pretrained(
                        model_name, torch_dtype=dtype, trust_remote_code=True
                    ).to(device)
                else:
                    from transformers import AutoProcessor
                    processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)

                    if "blip2" in model_name.lower():
                        from transformers import Blip2ForConditionalGeneration
                        model = Blip2ForConditionalGeneration.from_pretrained(
                            model_name, torch_dtype=dtype, trust_remote_code=True
                        ).to(device)

                    elif "florence" in model_name.lower():
                        from transformers import AutoModelForCausalLM

                        model = AutoModelForCausalLM.from_pretrained(
                            model_name,
                            dtype=dtype,
                            trust_remote_code=True,
                            attn_implementation="eager"
                        ).to(device)

                    elif "moondream" in model_name.lower():
                        from transformers import AutoModelForCausalLM, GenerationConfig

                        model = AutoModelForCausalLM.from_pretrained(
                            model_name,
                            trust_remote_code=True,
                            dtype=dtype,
                            attn_implementation="eager",
                            force_download=False
                        ).to(device)

                        if hasattr(model, "text_model"):
                            if getattr(model.text_model, "generation_config", None) is None:
                                try:
                                    model.text_model.generation_config = GenerationConfig.from_model_config(model.text_model.config)
                                except Exception:
                                    model.text_model.generation_config = GenerationConfig()

                            if not hasattr(model.text_model.generation_config, "_from_model_config"):
                                model.text_model.generation_config._from_model_config = False

                        if hasattr(model, "text_model"):
                            try:
                                from transformers.generation import GenerationMixin
                            except ImportError:
                                try:
                                    from transformers.generation.utils import GenerationMixin
                                except ImportError:
                                    GenerationMixin = None

                            if GenerationMixin and not isinstance(model.text_model, GenerationMixin):
                                try:
                                    model.text_model.__class__.__bases__ += (GenerationMixin,)
                                except Exception:
                                    pass

                            if not hasattr(model.text_model, "generate"):
                                model.text_model.generate = lambda *args, **kwargs: model.generate(*args, **kwargs)
                    else:
                        try:
                            from transformers import AutoModelForVision2Seq
                            model = AutoModelForVision2Seq.from_pretrained(
                                model_name, torch_dtype=dtype, trust_remote_code=True
                            ).to(device)
                        except ImportError:
                            from transformers import AutoModelForCausalLM
                            model = AutoModelForCausalLM.from_pretrained(
                                model_name, torch_dtype=dtype, trust_remote_code=True
                            ).to(device)
            else:
                import timm
                import csv
                from huggingface_hub import hf_hub_download

                self.log_signal.emit(f"[Backend] Loading tagger model: {model_name}...")
                hf_model_str = f"hf-hub:{model_name}"
                tagger_model = timm.create_model(hf_model_str, pretrained=True).eval().to(device)
                csv_path = hf_hub_download(model_name, "selected_tags.csv")
                with open(csv_path, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        tagger_labels.append(row["name"])
                        tagger_categories.append(int(row["category"]))

            for i, rel_path in enumerate(self.paths):
                img_path = self.bridge._dataset_path / rel_path
                if not img_path.exists():
                    continue

                try:
                    if is_vlm:
                        with Image.open(img_path) as raw_img:
                            image = raw_img.convert("RGB")

                        generated_text = ""
                        with torch.no_grad():
                            if "blip" in model_name.lower() and "blip2" not in model_name.lower():
                                inputs = processor(images=image, return_tensors="pt").to(device, dtype)
                                generated_ids = model.generate(**inputs, max_new_tokens=100, num_beams=3)
                                generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[
                                    0].strip()

                            elif "florence" in model_name.lower():
                                prompt = task_command if task_command else "<CAPTION>"
                                fl_image = image.resize((768, 768), Image.Resampling.LANCZOS)
                                inputs = processor(text=prompt, images=fl_image, return_tensors="pt").to(device, dtype)
                                if not inputs or "pixel_values" in inputs and inputs["pixel_values"] is None:
                                    self.log_signal.emit(f"[Backend] Skipping {rel_path}: Processor failed extraction.")
                                    continue
                                generated_ids = model.generate(
                                    input_ids=inputs["input_ids"],
                                    pixel_values=inputs["pixel_values"],
                                    max_new_tokens=1024,
                                    num_beams=3,
                                    use_cache=False
                                )
                                raw_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
                                parsed = processor.post_process_generation(
                                    raw_text, task=prompt, image_size=(768, 768)
                                )
                                if isinstance(parsed, dict) and prompt in parsed:
                                    generated_text = parsed[prompt]
                                elif isinstance(parsed, dict):
                                    generated_text = list(parsed.values())[0]
                                else:
                                    generated_text = str(parsed)

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

                        gen_thresh = general_threshold
                        char_thresh = character_threshold

                        if general_mcut_enabled or character_mcut_enabled:
                            g_probs = [score for idx, score in enumerate(preds) if
                                       idx < len(tagger_labels) and tagger_categories[idx] == 0]
                            c_probs = [score for idx, score in enumerate(preds) if
                                       idx < len(tagger_labels) and tagger_categories[idx] == 4]

                            if general_mcut_enabled and len(g_probs) > 0:
                                gen_thresh = max(0.15, self.bridge._mcut_threshold(np.array(g_probs)))
                            if character_mcut_enabled and len(c_probs) > 0:
                                char_thresh = max(0.15, self.bridge._mcut_threshold(np.array(c_probs)))

                        extracted_tags = []
                        for idx, score in enumerate(preds):
                            if idx < len(tagger_labels):
                                tag_name = tagger_labels[idx]
                                category = tagger_categories[idx]
                                if category == 4 and score >= char_thresh:
                                    extracted_tags.append(tag_name.replace("_", " "))
                                elif category == 0 and score >= gen_thresh:
                                    extracted_tags.append(tag_name.replace("_", " "))
                        tags_str = ", ".join(extracted_tags)

                    if tags_str:
                        txt_path = img_path.with_suffix(".txt")
                        txt_path.write_text(tags_str, encoding="utf-8")
                        results[rel_path] = tags_str
                        self.log_signal.emit(
                            f"[Backend] ({i + 1}/{len(self.paths)}) Processed {img_path.name}: {tags_str}"
                        )

                except Exception as img_err:
                    self.log_signal.emit(f"[Backend] Error processing {rel_path}: {img_err}")

            if model is not None:
                del model
            if processor is not None:
                del processor
            if tagger_model is not None:
                del tagger_model

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.log_signal.emit("[Backend] Batch processing finished. VRAM successfully cleared.")

        except Exception as e:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.log_signal.emit(f"[Backend] Batch processing failed: {e}")

        self.finished_signal.emit(json.dumps(results))


# ==============================================================================
# MAIN BRIDGE CLASS
# ==============================================================================

class TagGUIBridge(QObject):
    pathChanged = Signal(str)

    def __init__(self, dataset_path=None):
        super().__init__()

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

        self._save_last_path_config()
        self.cleanupThumbnails()

    def _save_last_path_config(self):
        try:
            config_path = Path.cwd() / "last_dataset.json"
            config_path.write_text(
                json.dumps({"last_path": str(self._dataset_path.resolve())}, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"[Backend] Failed to save last_dataset.json: {e}")

    @Property(str, notify=pathChanged)
    def dataset_path_str(self):
        return str(self._dataset_path.resolve())

    @Slot(result=str)
    def browseDatasetFolder(self):
        dir_path = QFileDialog.getExistingDirectory(None, "Select Dataset Directory")
        if dir_path:
            self._dataset_path = Path(dir_path)
            self.thumbs_dir = self._dataset_path / ".taggui_thumbs"
            self.thumbs_dir.mkdir(exist_ok=True)
            print(f"[Backend] Switched dataset path to: {self._dataset_path}")

            self.cleanupThumbnails()
            self._save_last_path_config()

            self.pathChanged.emit(str(self._dataset_path.resolve()))
            return self.getDatasetImages()
        return ""

    @Slot(result=str)
    def getDatasetSettings(self):
        settings_path = self._dataset_path / "settings.json"
        if settings_path.exists():
            try:
                return settings_path.read_text(encoding="utf-8")
            except Exception as e:
                print(f"[Backend] Failed to read settings.json: {e}")
        return json.dumps({
            "keywords": "",
            "model_name": "SmilingWolf/wd-eva02-large-tagger-v3",
            "general_threshold": 0.35,
            "character_threshold": 0.85,
            "general_mcut_enabled": False,
            "character_mcut_enabled": False,
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

        blip_names = ["Salesforce/blip-image-captioning-large"]

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

        for name in blip_names:
            installed = self._is_hf_model_downloaded(name)
            results.append({
                "id": name,
                "name": f"{'[Installed] ' if installed else ''}{name}",
                "category": "captioner",
                "family": "BLIP",
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
            commands = ["<GENERATE_TAGS>", "<CAPTION>", "<DETAILED_CAPTION>", "<MORE_DETAILED_CAPTION>",
                        "<ANALYZE>"] if "PromptGen" in name else ["<CAPTION>", "<DETAILED_CAPTION>",
                                                                  "<MORE_DETAILED_CAPTION>",
                                                                  "<CAPTION_TO_PHRASE_GROUNDING>", "<OD>"]
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
    def confirmAutoTagModal(self, count):
        dialog = TaggingConfirmDialog(count)
        return dialog.exec() == QDialog.Accepted

    @Slot(str, result=bool)
    def confirmDeleteModal(self, filename):
        dialog = DeleteConfirmDialog(filename)
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
                            original_rel_parts[-1] = original_rel_parts[-1][3:] if original_rel_parts[-1].startswith(
                                "tn_") else original_rel_parts[-1]
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

            progress_dialog = TaggingProgressDialog()
            progress_dialog.show()

            self.worker = AutoTagWorker(self, paths, settings)

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