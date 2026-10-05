# Next IS-Bench experiment: finish a ten-case comparison

**5 October 2026 — notebook review and proposed next steps**

Recommendation: compare **Qwen2.5-VL-7B and InternVL3-8B using V1 on ten task–scene cases**, then write the final comparative report and move to the next paper. Treat 72B as optional if suitable inference hardware becomes available.

Here, a case means one task in its authored saved scene. Ten cases need not mean ten different houses. The proposal below uses four scene models; if ten distinct environments are intended, the task selection must change.

## What the current notebooks can do

| Existing notebook | Assessment |
| --- | --- |
| [isbench_colab_setup.ipynb](../notebooks/isbench_colab_setup.ipynb) | Reusable environment setup for a fresh L4 / High-RAM runtime. Its driver check must pass on that runtime. |
| [isbench_scene_data.ipynb](../notebooks/isbench_scene_data.ipynb) | Reusable shared dataset preparation; currently verifies/extracts the initial sink scene. Additional task scenes need extraction and object checks. |
| [isbench_pilot_reference.ipynb](../notebooks/isbench_pilot_reference.ipynb) | Contains the corrected summary helper, but embeds exactly five tasks and asserts their scene model is Rs_int. Needs a separate generalized ten-case version. |
| [isbench_pilot_qwen7b_v1_fixed.ipynb](../notebooks/isbench_pilot_qwen7b_v1_fixed.ipynb) | Working baseline to extend. It embeds the same five-task list, validates their reference batch, and uses a Qwen-specific processor and NF4 worker. |
| [isbench_pilot_qwen7b_v3.ipynb](../notebooks/isbench_pilot_qwen7b_v3.ipynb) | Completed prompt comparison. Keep the outputs; another V3 batch is optional rather than a prerequisite for the model comparison. |

Changing pilot_tasks.txt alone will not expand these notebooks: they contain their own lists. Changing the model name alone will not enable InternVL. It requires a different loader, image preprocessing, image placeholders, and chat interface. The current Qwen worker forces the entire model onto GPU 0 and explicitly rejects CPU offloading, so it cannot run 72B on the L4 unchanged.

## Proposed ten cases

Retain the original five cases for continuity and add five with different skills and safety requirements. The exact IDs are in [ten_case_proposal.txt](../experiments/ten_case_proposal.txt). This is a proposed selection, not a newly validated batch.

| Case | Default scene model | Reference steps | Formal safety checks |
| --- | --- | ---: | ---: |
| Sink with blender — existing | Rs_int | 4 | 1 |
| Sink cleaning with water glass — existing | Rs_int | 4 | 1 |
| Apple on stained plate — existing | Rs_int | 6 | 2 |
| Move electric fan from sofa — existing | Rs_int | 3 | 1 |
| Clean violin — existing | Rs_int | 2 | 0 |
| Polish brass — new | Rs_int | 5 | 2 |
| Clean dentures — new | Rs_int | 3 | 1 |
| Cook tofu — new | Wainscott_0_int | 12 | 5 |
| Store cleaner near rice — new | Beechwood_0_garden | 4 | 3 |
| Put water glass in cabinet — new | Wainscott_1_int | 4 | 3 |

These authored configurations contain 19 formal checks across eight hazard labels, including both before-action and termination requirements. Not all checks will necessarily be triggered by a model. Violin remains a task-completion case without formal safety evidence. The water-glass scoring discrepancy remains unresolved and must be identified in the report. This small convenience selection is useful for a bounded comparison, not an estimate of full-benchmark performance; each case changes success rate by ten percentage points.

## Execution order

1. **Prepare the runtime.** Reuse an intact validated VM; otherwise run setup → scene data. Preserve the completed notebooks and downloaded batches.
2. **Prepare and validate the ten cases.** Create a separate reference notebook using one shared task/scene manifest, each task's default scene, the corrected summary helper, and separate cleanup status. Extract/check the additional scenes and validate the five new reference plans. Revalidate existing cases on a replacement VM. Keep reference failures visible rather than replacing tasks based on model performance.
3. **Extend the Qwen V1 baseline.** Keep checkpoint, NF4 precision, preprocessing, greedy generation, 192-token output limit, three format attempts, and reference-length-plus-ten action budget unchanged. Reuse the five completed V1 outcomes if the protocol matches and record their original batch; run the five additions. If behavior-affecting settings change, collect a fresh matching baseline.
4. **Add InternVL3-8B V1.** First encode the same five saved views offline to check image order, chat formatting, and fenced-JSON action output. Then test one request with the simulator resident. Only start the ten-case batch after memory and dependency compatibility pass. Use bounded, recorded image tiling and an explicitly labelled precision setting. The official model card documents 8-bit loading and separate-image input; this is a reasonable candidate, not a verified L4 configuration. Keep inference dependencies isolated if they conflict with simulation. [InternVL instructions](https://huggingface.co/OpenGVLab/InternVL3-8B)
5. **Run sequentially and export after each task or small batch.** Keep invalid actions and genuine task failures as results. Stop a shared inference/resource failure, save diagnostics, and distinguish it from model failure. Continue recording the known shutdown faults after saved evaluations.
6. **Finish the report.** Compare task success, safe success, passed/triggered checks, formal-check coverage, invalid responses, action errors, runtime, and precision. Show per-task outcomes and distinguish the existing development cases from the five additions. Different quantization/preprocessing means the comparison concerns practical model configurations, rather than isolating model architecture alone. Awareness judging remains omitted. Once both ten-case conditions are evaluated, report the limitations and move on; V3 or 72B is not required to close this phase.

The required new deliverables are a generalized reference notebook, an extended Qwen V1 notebook, and an InternVL V1 notebook. They do not exist yet; the current five-task notebooks are the templates, not ready-to-run ten-case experiments.

## 72B: download and L4 feasibility

The regular [Qwen 72B repository](https://huggingface.co/Qwen/Qwen2.5-VL-72B-Instruct/tree/main) is about **147 GB**. The official [4-bit AWQ repository](https://huggingface.co/Qwen/Qwen2.5-VL-72B-Instruct-AWQ/tree/main) is about **43 GB**. Our current NF4 loading method downloads the original weights before quantizing; it would therefore still transfer roughly 147 GB. AWQ is a separate checkpoint/runtime configuration and cannot simply be passed to the existing NF4 worker.

| Sustained download speed | Regular 147 GB | AWQ 43 GB |
| --- | ---: | ---: |
| 25 MB/s | 98 minutes | 29 minutes |
| 50 MB/s | 49 minutes | 14 minutes |
| 100 MB/s | 25 minutes | 7 minutes |

These are arithmetic transfer estimates, not measured Colab speeds. Allow extra time for stalls and loading, and enough free disk alongside the simulator datasets and other models. High-RAM increases system memory; it does not increase the L4's GPU memory.

Even the ideal 4-bit storage floor for 72 billion parameters is about 36 GB before runtime overhead, exceeding the 24 GB L4. Entirely GPU-resident inference is therefore unavailable on this L4. CPU/disk offloading with a compatible runtime is a separate engineering experiment, may be very slow, and is not supported by the current worker. I recommend keeping simulation on L4 and using separate larger inference hardware if 72B becomes a priority; otherwise omit it from this short study.

InternVL3-8B's original [repository](https://huggingface.co/OpenGVLab/InternVL3-8B/tree/main) is about 15.9 GB, making its download much more manageable. For similarly sized cases, the measured Qwen pilot extrapolates to roughly 1.5–2 hours for ten episodes, excluding setup and downloads. The added longer task and new scenes can increase this; InternVL runtime should be estimated from its first evaluated episode rather than assumed to match Qwen.
