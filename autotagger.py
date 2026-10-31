import csv
import gc
import json
from pathlib import Path
import numpy as np
import torch
from PIL import Image
from PySide6.QtCore import QThread, Signal
from huggingface_hub import hf_hub_download


class AutoTagWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(str)

    def __init__(self, bridge, paths, settings):
        super().__init__()
        self.bridge = bridge
        self.paths = paths
        self.settings = settings
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True
        self.requestInterruption()

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

                    elif "joycaption" in model_name.lower() or "llava" in model_name.lower():
                        from transformers import AutoProcessor, LlavaForConditionalGeneration
                        processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
                        model = LlavaForConditionalGeneration.from_pretrained(
                            model_name, torch_dtype=dtype, trust_remote_code=True
                        ).to(device)

                    elif "florence" in model_name.lower():
                        from transformers import AutoModelForCausalLM, GenerationConfig

                        model = AutoModelForCausalLM.from_pretrained(
                            model_name,
                            torch_dtype=dtype,
                            trust_remote_code=True,
                            attn_implementation="eager"
                        ).to(device)

                        # --- ROBUST CONFIG FIX FOR COGFLORENCE-2 ---
                        for target_obj in [model, getattr(model, "language_model", None)]:
                            if target_obj is not None:
                                if getattr(target_obj, "generation_config", None) is None:
                                    try:
                                        target_obj.generation_config = GenerationConfig.from_model_config(target_obj.config)
                                    except Exception:
                                        target_obj.generation_config = GenerationConfig()

                                if not hasattr(target_obj.generation_config, "_from_model_config"):
                                    target_obj.generation_config._from_model_config = False
                        # -------------------------------------------

                        # Safety patch if missing generation mixin/attributes
                        if hasattr(model, "language_model"):
                            try:
                                from transformers.generation import GenerationMixin
                            except ImportError:
                                try:
                                    from transformers.generation.utils import GenerationMixin
                                except ImportError:
                                    GenerationMixin = None

                            if GenerationMixin and not isinstance(model.language_model, GenerationMixin):
                                try:
                                    model.language_model.__class__.__bases__ += (GenerationMixin,)
                                except Exception:
                                    pass

                            if not hasattr(model.language_model, "generate"):
                                model.language_model.generate = lambda *args, **kwargs: model.generate(*args, **kwargs)

                    # ---  QWEN LOADING BLOCK  ---
                    elif "qwen" in model_name.lower():
                        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration, AutoModelForCausalLM

                        # 1. Safe Processor Load with fallback
                        try:
                            processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
                        except Exception:
                            # If config.json lacks model_type, force Qwen2/3-VL processor resolution
                            processor = AutoProcessor.from_pretrained(
                                model_name,
                                trust_remote_code=True,
                                model_type="qwen2_vl"
                            )

                        # 2. Safe Model Load with explicit Qwen VL classes fallback
                        try:
                            from transformers import AutoModelForVision2Seq
                            model = AutoModelForVision2Seq.from_pretrained(
                                model_name,
                                torch_dtype=dtype,
                                trust_remote_code=True
                            ).to(device)
                        except Exception:
                            try:
                                # Direct fallback for Qwen VL architectures
                                model = Qwen2VLForConditionalGeneration.from_pretrained(
                                    model_name,
                                    torch_dtype=dtype,
                                    trust_remote_code=True
                                ).to(device)
                            except Exception:
                                model = AutoModelForCausalLM.from_pretrained(
                                    model_name,
                                    torch_dtype=dtype,
                                    trust_remote_code=True
                                ).to(device)
                    # ----------------------------------------

                    elif "moondream" in model_name.lower():
                        from transformers import AutoModelForCausalLM, GenerationConfig

                        model = AutoModelForCausalLM.from_pretrained(
                            model_name,
                            trust_remote_code=True,
                            torch_dtype=dtype,
                            attn_implementation="eager",
                            force_download=False
                        ).to(device)

                        if hasattr(model, "text_model"):
                            if getattr(model.text_model, "generation_config", None) is None:
                                try:
                                    model.text_model.generation_config = GenerationConfig.from_model_config(
                                        model.text_model.config)
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
                if self._is_cancelled or self.isInterruptionRequested():
                    self.log_signal.emit("[Backend] Process aborted by user. Cleaning up...")
                    break

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
                                prompt = "A detailed, descriptive caption of this image with background details:"
                                inputs = processor(images=image, text=prompt, return_tensors="pt").to(device, dtype)
                                generated_ids = model.generate(
                                    **inputs,
                                    max_new_tokens=150,
                                    min_length=30,
                                    do_sample=True,
                                    temperature=0.7,
                                    repetition_penalty=1.2,
                                    num_beams=3
                                )

                                # Slice off the input prompt token IDs so only the newly generated caption remains
                                input_len = inputs["input_ids"].shape[1]
                                generated_text = processor.batch_decode(
                                    generated_ids[:, input_len:],
                                    skip_special_tokens=True
                                )[0].strip()

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

                            # --- ADD THIS QWEN GENERATION BLOCK HERE ---
                            elif "qwen" in model_name.lower():
                                prompt = task_command if task_command else "Write a descriptive caption for this image."
                                convo = [
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "image"},
                                            {"type": "text", "text": prompt},
                                        ],
                                    }
                                ]
                                text_prompt = processor.apply_chat_template(
                                    convo,
                                    tokenize=False,
                                    add_generation_prompt=True
                                )
                                inputs = processor(
                                    text=[text_prompt],
                                    images=[image],
                                    padding=True,
                                    return_tensors="pt"
                                ).to(device)

                                if "pixel_values" in inputs and inputs["pixel_values"] is not None:
                                    inputs["pixel_values"] = inputs["pixel_values"].to(dtype)

                                output_ids = model.generate(
                                    **inputs,
                                    max_new_tokens=256,
                                    do_sample=True,
                                    temperature=0.6
                                )

                                input_len = inputs["input_ids"].shape[1]
                                decoded_outputs = processor.batch_decode(
                                    output_ids[:, input_len:],
                                    skip_special_tokens=True
                                )
                                generated_text = decoded_outputs[0].strip() if decoded_outputs else ""
                            # ---------------------------------------------



                            elif "joycaption" in model_name.lower() or "llava" in model_name.lower():
                                prompt = task_command if task_command else "Write a descriptive caption for this image."

                                convo = [
                                    {"role": "system", "content": "You are a helpful image captioner."},
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "image"},
                                            {"type": "text", "text": prompt},
                                        ],
                                    },
                                ]

                                text_prompt = processor.apply_chat_template(
                                    convo,
                                    tokenize=False,
                                    add_generation_prompt=True
                                )

                                if isinstance(text_prompt, list):
                                    text_prompt = text_prompt[0]

                                text_prompt = str(text_prompt)

                                inputs = processor(
                                    text=[text_prompt],
                                    images=[image],
                                    return_tensors="pt"
                                ).to(device)

                                if "pixel_values" in inputs and inputs["pixel_values"] is not None:
                                    inputs["pixel_values"] = inputs["pixel_values"].to(dtype)

                                output_ids = model.generate(
                                    **inputs,
                                    max_new_tokens=256,
                                    do_sample=True,
                                    temperature=0.6
                                )

                                input_len = inputs["input_ids"].shape[1]
                                decoded_outputs = processor.batch_decode(
                                    output_ids[:, input_len:],
                                    skip_special_tokens=True
                                )
                                generated_text = decoded_outputs[0].strip() if decoded_outputs else ""

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

            if self._is_cancelled:
                self.log_signal.emit("[Backend] Aborted successfully. VRAM successfully cleared.")
            else:
                self.log_signal.emit("[Backend] Batch processing finished. VRAM successfully cleared.")

        except Exception as e:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.log_signal.emit(f"[Backend] Batch processing failed: {e}")

        self.finished_signal.emit(json.dumps(results))