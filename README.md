# IS-Bench Open-Weight Model Evaluation

An ongoing, independent reproduction of [IS-Bench](https://github.com/AI45Lab/IS-Bench), studying whether vision-language models can complete household tasks safely in simulation. This project contains the Colab workflow, experiment helpers, and saved pilot results.

## Progress

- Built an NVIDIA L4 Colab environment with OmniGibson 1.1.1 and Isaac Sim 4.1, resolving graphics, package, and scene-data issues.
- Validated the authors' reference plans on five tasks; corrected summaries confirm **5/5 passes**.
- Investigated Qwen2.5-VL-3B sink failures using prompt variants, executor feedback, and fixed-image diagnostics.
- Completed paired five-task Qwen2.5-VL-7B-Instruct pilots with NF4 quantization.

| Metric | V1: baseline prompt | V3: safety reminders |
| --- | --- | --- |
| Task success | 40% (2/5) | 40% (2/5) |
| Safe task success | 20% (1/5) | 20% (1/5) |
| Safety recall: passed / triggered checks | 25% (1/4) | 40% (2/5) |

These are small pilot results, not a full benchmark reproduction. The only safe completion was a task without formal safety checks. A scene-state discrepancy prevents attributing the recall increase to the prompt; safety awareness was not measured. See the [result index](results/README.md) and [comparison analysis](docs/qwen7b_v1_v3_pilot_results_analysis.md).

## Run the current pilot

Use an **L4, High-RAM Colab runtime**, running these notebooks in order on the same runtime:

1. [Environment setup](notebooks/isbench_colab_setup.ipynb)
2. [Scene and asset preparation](notebooks/isbench_scene_data.ipynb)
3. [Five-task reference validation](notebooks/isbench_pilot_reference.ipynb)
4. [Qwen 7B V1 pilot](notebooks/isbench_pilot_qwen7b_v1_fixed.ipynb)
5. Optional: [Qwen 7B V3 comparison](notebooks/isbench_pilot_qwen7b_v3.ipynb)

The notebooks embed their helper code and download the pinned upstream repository, assets, and model at runtime. Uploading the notebook is sufficient; weights and simulator assets are not bundled here. Export results before the temporary Colab runtime expires.

## Project layout and next step

- `notebooks/`: five reusable notebooks with saved outputs cleared.
- `scripts/`: six current helper scripts for inspection and development; notebooks contain embedded copies.
- `experiments/`: current five-task list and proposed ten-case list.
- `docs/`: [progress report](docs/progress_report.md), analyses, [notebook guide](docs/notebook_guide.md), and [next experiment plan](docs/next_experiment_plan.md).
- `results/`: compact summaries and audits committed to Git.

Task definitions, prompts, primitives, and evaluation originate from [AI45Lab/IS-Bench](https://github.com/AI45Lab/IS-Bench/tree/6a406e162feca1c4c455d9c9f1f58832edbdc1fd); this project adds environment setup, local inference, diagnostics, and result analysis. Scene data comes from the [authors' dataset](https://huggingface.co/datasets/Ursulalala/IS_Bench_dataset). Follow the respective upstream terms when using code, models, and assets.
