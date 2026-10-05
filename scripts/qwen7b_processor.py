"""Load the pinned 7B processor with Transformers 4.51.3's image class.

The checkpoint says Qwen2_5_VLImageProcessor, while this Transformers version
uses Qwen2VLImageProcessor for qwen2_5_vl. Read the original numerical settings
and multimodal chat template without editing cached checkpoint files.
"""
import hashlib
import json
from pathlib import Path


def load_processor(model_path):
    from transformers import AutoTokenizer, Qwen2VLImageProcessor, Qwen2_5_VLProcessor

    model_path = Path(model_path)
    config_file = model_path / "preprocessor_config.json"
    config = json.loads(config_file.read_text())
    declared = config.get("image_processor_type")
    if declared not in ("Qwen2_5_VLImageProcessor", "Qwen2VLImageProcessor"):
        raise ValueError(f"Unexpected image processor in pinned checkpoint: {declared}")
    image_processor = Qwen2VLImageProcessor.from_pretrained(
        str(model_path), min_pixels=256 * 28 * 28, max_pixels=512 * 28 * 28,
        local_files_only=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    # The tokenizer's separate template is text-only at this revision. Use the
    # checkpoint's processor template, which handles lists of image/text parts.
    template_file = model_path / "chat_template.json"
    template = json.loads(template_file.read_text())["chat_template"]
    if not isinstance(template, str) or "<|image_pad|>" not in template:
        raise ValueError("Expected the checkpoint's multimodal chat template.")
    processor = Qwen2_5_VLProcessor(
        image_processor=image_processor, tokenizer=tokenizer, chat_template=template,
    )
    provenance = {
        "checkpoint_image_processor_type": declared,
        "loaded_image_processor_class": type(image_processor).__name__,
        "loaded_processor_class": type(processor).__name__,
        "min_pixels": image_processor.min_pixels, "max_pixels": image_processor.max_pixels,
        "preprocessor_config_sha256": hashlib.sha256(config_file.read_bytes()).hexdigest(),
        "chat_template_file_sha256": hashlib.sha256(template_file.read_bytes()).hexdigest(),
        "compatibility_fix": "explicit Qwen2VLImageProcessor with original multimodal template",
    }
    return processor, provenance
