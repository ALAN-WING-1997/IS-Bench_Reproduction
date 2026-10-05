# 7B pilot loading failure and repair

The downloaded run `20261002T033642_018933Z` did not produce a model outcome. Runtime verification passed on NVIDIA L4, all five corrected reference validations passed, and the pinned 7B weights downloaded. The sink scene loaded and saved five initial observations. The first inference request failed while loading the image processor, before loading model weights into GPU memory, generating an action or executing an action. The run stopped after about 96 seconds. Only one of five tasks was attempted; zero valid evaluations were saved. SR, SSR and SRec are unavailable, not zero.

The primary error in `clean_a_kitchen_sink__with_blender/response_001.json` is `ValueError: Unrecognized image processor`. The pinned checkpoint declares `Qwen2_5_VLImageProcessor`, but Transformers 4.51.3 maps qwen2_5_vl to `Qwen2VLImageProcessor`. The later native crash occurs during `og.shutdown()` after the inference failure and is a separate unresolved cleanup problem.

## Repair

`qwen7b_processor.py` explicitly constructs the compatible image class from the checkpoint's original numerical settings, with the same pixel bounds as the previous notebook. It uses the original `chat_template.json` multimodal template; the checkpoint's tokenizer template is text-only and cannot be substituted. Cached checkpoint files are not modified. No weights, precision, prompt or task selection changed.

`isbench_pilot_qwen7b_v1_fixed.ipynb` is a separate notebook, preserving the executed original notebook and downloaded run. Its second code cell now processes five saved reference observations before opening a simulator, records processor/template hashes, and requires `PROCESSOR_PREFLIGHT_OK`. It embeds the new helper and revised runner. Inference exceptions are included directly in progress/summary output so shutdown stack traces no longer obscure them.

## Verification

A temporary CPU environment using Transformers 4.51.3 reproduced the original AutoProcessor error against the exact pinned checkpoint configuration. The revised loader then encoded all five actual initial observation images successfully: 2,433 input tokens for the short diagnostic prompt; image grids were [1, 32, 60] each. The numerical pixel bounds were 200,704–401,408. All checkpoint file hashes were unchanged. This checks image loading and template handling; it does not validate GPU weight loading, quantization or model generation. Details are saved in `qwen7b_processor_fix_validation.json`.

The six notebook cells, model preparation script and four embedded helper scripts compile. Eight regression checks passed for generic execution of all five tasks, original V1 prompt preservation, invalid-format retries, action limits, handling action errors, separating infrastructure failures from model failures, formal safety denominators, DONE normalization of the five real reference runs and batch stop/continue behavior.

## Next run

On the existing prepared L4 runtime, upload the fixed notebook and execute its six code cells in order. Existing scene files, reference reports and cached model weights are reused; no setup or reference rerun is required. If the runtime has been replaced, run environment setup, scene data, five reference validations and then the fixed notebook on the same VM. After cell 2 reports `PROCESSOR_PREFLIGHT_OK` and `QWEN7B_WEIGHTS_READY`, cell 4 tests full 7B inference alongside the live scene. Cell 5 runs the remaining tasks only when an evaluated outcome was saved. Cell 6 exports complete or partial results. Preserve the failed run as infrastructure evidence rather than a model score.

## Primary sources

- [Pinned checkpoint processor config](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct/blob/bfb8829e3c6c0ebad5da954181947bb9df50b0e0/preprocessor_config.json)
- [Transformers 4.51.3 image mapping](https://github.com/huggingface/transformers/blob/v4.51.3/src/transformers/models/auto/image_processing_auto.py)
- [Transformers Qwen2.5 processor implementation](https://github.com/huggingface/transformers/blob/v4.51.3/src/transformers/models/qwen2_5_vl/processing_qwen2_5_vl.py)
