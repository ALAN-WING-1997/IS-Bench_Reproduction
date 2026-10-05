# Notebook guide

The five notebooks in `notebooks/` are the current workflow. Run them in order on the same L4, High-RAM Colab runtime.

| Notebook | Purpose |
| --- | --- |
| [isbench_colab_setup.ipynb](../notebooks/isbench_colab_setup.ipynb) | Install and verify the GPU simulation environment. |
| [isbench_scene_data.ipynb](../notebooks/isbench_scene_data.ipynb) | Download assets, pin upstream code, and prepare scene data. |
| [isbench_pilot_reference.ipynb](../notebooks/isbench_pilot_reference.ipynb) | Execute the authors' plans on the five pilot tasks and check the evaluator. |
| [isbench_pilot_qwen7b_v1_fixed.ipynb](../notebooks/isbench_pilot_qwen7b_v1_fixed.ipynb) | Run the working Qwen 7B baseline with the repaired processor. |
| [isbench_pilot_qwen7b_v3.ipynb](../notebooks/isbench_pilot_qwen7b_v3.ipynb) | Optional paired comparison using explicit safety reminders. |

These are reusable templates with saved outputs cleared. Their code is unchanged from the working versions. Original executed copies are retained locally under `archive/notebooks/`; previous result files are retained under `results/raw/`. Those folders are excluded from Git. Published summaries and audits are indexed in [results](../results/README.md).

The notebooks embed helper scripts, so they can run without uploading the `scripts/` folder. When changing a helper, also update the corresponding embedded copy before running the notebook. The V3 notebook carries its own prompt-specific version.

## What was cleaned up

- Older 3B sink experiments, diagnostics, Drive utilities, the superseded environment check, and the failed first 7B notebook were moved into the local archive.
- Deleted `simulation_env_check.ipynb`, whose cells and outputs are duplicated by the retained `simulation_env_check_new.ipynb`.
- Deleted five obsolete standalone helpers: `drive_archive.py`, `qwen_next_action.py`, `run_sink_qwen.py`, `run_sink_qwen_feedback.py`, and `run_sink_reference.py`. Their source is preserved inside the archived notebooks.
- Removed generated Python caches and macOS metadata.

No saved run was deleted. `archive/migration_manifest.json` records where the original files went and their hashes.

The active model notebooks currently run **five tasks**. The ten-case list is a proposal, and InternVL support still needs implementation; see the [next experiment plan](next_experiment_plan.md).
