"""Isolated 7B NF4 request; no simulator imports or CPU offloading."""
import argparse
import json
from pathlib import Path
import time
import traceback


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def main(request_file, response_file, model_path):
    import torch
    import bitsandbytes as bnb
    from transformers import BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration
    from qwen_vl_utils import process_vision_info
    from qwen7b_processor import load_processor

    assert torch.cuda.is_available(), "CUDA is unavailable in the inference environment."
    request = json.loads(request_file.read_text())
    assert len(request["images"]) == 5
    free_bytes, total_bytes = torch.cuda.mem_get_info()
    # Conservative preflight, checked while the simulator scene is resident.
    if free_bytes < 8 * 1024**3:
        raise RuntimeError(f"Only {free_bytes / 1024**3:.1f} GiB free beside the simulator; need at least 8 GiB.")
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    processor, processor_info = load_processor(model_path)
    quantization = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16,
        llm_int8_skip_modules=["visual", "lm_head"],
    )
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_path, torch_dtype=torch.float16, device_map={"": 0},
        quantization_config=quantization, attn_implementation="sdpa",
        local_files_only=True,
    ).eval()
    quantized_count = sum(isinstance(m, bnb.nn.Linear4bit) for m in model.modules())
    assert model.is_loaded_in_4bit and quantized_count > 0, "4-bit conversion did not take effect."
    assert not any(isinstance(m, bnb.nn.Linear4bit) for m in model.visual.modules()), "Vision encoder must remain FP16."
    device_map = {k: str(v) for k, v in model.hf_device_map.items()}
    assert all(v in ("0", "cuda:0") for v in device_map.values()), "Unexpected CPU/disk offloading."
    messages = [{"role": "user", "content": [
        *[{"type": "image", "image": Path(p).resolve().as_uri()} for p in request["images"]],
        {"type": "text", "text": request["prompt"]},
    ]}]
    chat = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    images, videos = process_vision_info(messages)
    inputs = processor(text=[chat], images=images, videos=videos,
                       padding=True, return_tensors="pt").to("cuda")
    with torch.inference_mode():
        generated = model.generate(**inputs, max_new_tokens=192, do_sample=False)
    torch.cuda.synchronize()
    answer = processor.batch_decode(
        generated[:, inputs.input_ids.shape[1]:], skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0]
    after_free, _ = torch.cuda.mem_get_info()
    result = {
        "raw_output": answer, "inference_seconds_including_model_load": time.monotonic() - started,
        "input_tokens": int(inputs.input_ids.shape[1]),
        "gpu_free_before_model_bytes": free_bytes, "gpu_total_bytes": total_bytes,
        "gpu_free_after_generation_bytes": after_free,
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        "model_memory_footprint_bytes": model.get_memory_footprint(),
        "device_map": device_map, "quantized_linear_count": quantized_count,
        "processor": processor_info,
        "quantization": {"format": "nf4", "double_quant": True, "compute_dtype": "float16",
                         "unquantized_modules": ["visual", "lm_head"]},
    }
    save_json(response_file, result)
    print("QWEN_RESPONSE_SAVED", answer, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--model-path", required=True)
    args = parser.parse_args()
    try:
        main(args.request, args.response, args.model_path)
    except Exception:
        save_json(args.response, {"error": traceback.format_exc()})
        raise
