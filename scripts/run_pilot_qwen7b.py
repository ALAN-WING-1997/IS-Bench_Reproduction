"""One pilot task with Qwen 7B NF4, original V1 prompt and IS-Bench evaluator."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
from unittest.mock import patch


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


class DisabledJudge:
    def __getattr__(self, name):
        raise RuntimeError("Proprietary API judging is disabled.")


def parse_plan(raw, allowed, objects):
    # Match the authors' fenced-JSON parser; do not silently repair model plans.
    matches = re.findall(r"```json(.*?)```", raw, re.DOTALL)
    if not matches:
        return None
    try:
        candidate = json.loads(matches[0].strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(candidate, dict) or not isinstance(candidate.get("action"), str):
        return None
    action = candidate["action"].strip()
    caution = candidate.get("caution")
    if caution is not None and not isinstance(caution, str):
        return None
    if action.upper().startswith("DONE"):
        return {"action": "done()", "caution": caution}
    matches = re.findall(r"(?:\d+\.\s+)?([a-zA-Z_]+)\(([^)]+)\)", action)
    if not matches:
        return None
    operator, params = matches[-1]
    operator = operator.strip().upper()
    args = [p.strip().lower() for p in params.split(",")]
    if operator not in allowed or len(args) != allowed[operator]:
        return None
    if any(p not in objects for p in args):
        return None
    return {"action": f"{operator.lower()}({', '.join(args)})", "caution": caution}


def make_prompt(repo, task, history, prompt_setting="v1"):
    spec = importlib.util.spec_from_file_location("isbench_prompts", repo / "og_ego_prim/utils/prompts.py")
    prompts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prompts)
    context = task["planning_context"]
    abilities = context["object_abilities"]
    if prompt_setting not in ("v1", "v3"):
        raise ValueError(f"Unsupported prompt setting: {prompt_setting}")
    fields = dict(
        objects_str="\n".join(f"{i+1}. {obj.strip()}" for i, obj in enumerate(context["object_list"])),
        task_instruction=context["task_instruction"],
        object_abilities_str="" if abilities is None else "\n".join(f"{k}: {v}" for k, v in abilities.items()),
        task_goals=task["evaluation_goal_conditions"]["execution_goal_condition"],
        wash_rules_str="" if context["wash_rules"] is None else json.dumps(context["wash_rules"], indent=4, ensure_ascii=False),
        history_actions="None" if not history else "\n".join(history),
    )
    if prompt_setting == "v3":
        # Preserve the authors' source ordering and safety-tip wording.
        goals = task["evaluation_goal_conditions"]
        tips = [tip["safety_tip"] for tip in task["evaluation_cautions"]]
        tips.extend(tip["safety_tip"] for tip in goals["process_safety_goal_condition"])
        tips.extend(tip["safety_tip"] for tip in goals["termination_safety_goal_condition"])
        fields["safety_tips"] = json.dumps(tips, indent=4, ensure_ascii=False)
        return prompts.V3StepPlanningPrompt.format(**fields)
    return prompts.V1StepPlanningPrompt.format(**fields)


def run_episode(repo, output, worker, model_path, max_steps, task_name, scene="Rs_int", prompt_setting="v1"):
    os.environ.pop("OMNIGIBSON_NO_OMNIVERSE", None)
    os.environ["OMNI_KIT_ACCEPT_EULA"] = "YES"
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "bddl"))
    # Isaac Sim later changes library paths in its process. Keep the original
    # environment for the independent inference child.
    inference_env_base = os.environ.copy()
    progress = {"phase": "loading_scene", "task": task_name, "scene": scene, "attempts": []}
    save_json(output / "progress.json", progress)
    benchmark = None
    try:
        import omnigibson as og
        from omnigibson.macros import gm
        gm.HEADLESS = True
        gm.USE_GPU_DYNAMICS = True
        from og_ego_prim.utils.monkey_patch import add_monkey_patch
        add_monkey_patch()
        from og_ego_prim.benchmark import build_benchmark
        from og_ego_prim.primitives.ego_primitives import VALID_PRIMITIVES

        task = json.loads((repo / "data/tasks" / f"{task_name}.json").read_text())
        save_json(output / "task_config.json", task)
        assert task["scene_info"]["default_scene_model"] == scene
        assert max_steps == len(task["example_planning"]) + 10
        with patch.dict(os.environ, {"OPENAI_API_KEY": "disabled", "OPENAI_API_BASE": "http://127.0.0.1:9"}), \
                patch("openai.OpenAI", return_value=DisabledJudge()):
            benchmark = build_benchmark(
                task=task_name, scene=scene, ego_view=True, online_object_sampling=False,
                debug=False, eval_process_safety=True, eval_termination_safety=True,
                eval_execution=True, eval_awareness=False,
            )
        benchmark.tracker.model = "Qwen2.5-VL-7B-Instruct-NF4"
        expected_scene = repo / f"data/scenes/{scene}/json/{scene}_task_{task_name}_0_0_template.json"
        assert Path(benchmark.env_config["scene"]["scene_file"]).resolve() == expected_scene.resolve()

        def views(label):
            folder = output / label
            observations = benchmark.get_surrounding_viewer_obs(save_img=str(folder))
            if observations is None or len(observations) != 5:
                raise RuntimeError("Expected five surrounding views.")
            return [str(folder / f"obs_{i}.png") for i in range(5)]

        images = views("00_initial")
        history = []
        progress["phase"] = "model_planning"
        save_json(output / "progress.json", progress)
        request_number = 0
        for step in range(1, max_steps + 1):
            prompt = make_prompt(repo, task, history, prompt_setting)
            plan = None
            for retry in range(3):
                request_number += 1
                request_file = output / f"request_{request_number:03d}.json"
                response_file = output / f"response_{request_number:03d}.json"
                save_json(request_file, {
                    "step": step, "retry": retry, "images": images, "prompt": prompt,
                    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "image_sha256": {str(p): hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in images},
                })
                # Start a fresh inference process per request. Its exit releases
                # model GPU memory before the simulator executes the next action.
                inference_env = inference_env_base.copy()
                inference_env["OMNIGIBSON_NO_OMNIVERSE"] = "1"
                print(f"QWEN_REQUEST: step {step}, attempt {retry+1}", flush=True)
                subprocess.run([
                    sys.executable, str(worker), "--request", str(request_file),
                    "--response", str(response_file), "--model-path", str(model_path),
                ], env=inference_env, check=True, timeout=900)
                response = json.loads(response_file.read_text())
                plan = parse_plan(response["raw_output"], VALID_PRIMITIVES, task["planning_context"]["object_list"])
                benchmark.tracker.track_raw_output(step=step, content=response["raw_output"])
                progress["attempts"].append({"request": request_number, "step": step, "valid_plan": plan is not None})
                save_json(output / "progress.json", progress)
                benchmark.tracker.save_tracking(str(output / "report_partial.json"))
                if plan is not None:
                    break
            if plan is None:
                benchmark.tracker.track_termination(reason="plan_error", msg="Three invalid fenced-JSON action proposals.")
                break
            benchmark.tracker.track_plan(step=step, plan=plan)
            history.append(f"{step}. {plan['action'].split('(')[0].upper()}({plan['action'].split('(', 1)[1]}")
            print(f"MODEL_ACTION {step}: {plan['action']}", flush=True)
            progress["phase"] = "executing_model_action"
            save_json(output / "progress.json", progress)
            benchmark.execute_plan(plan)  # Upstream logs action failures and continues.
            benchmark.tracker.save_tracking(str(output / "report_partial.json"))
            label = f"{step:02d}_{plan['action'].split('(')[0]}"
            if plan["action"].startswith("done"):
                benchmark.tracker.track_termination(reason="done")
                break
            images = views(label)
            progress["phase"] = "model_planning"
            save_json(output / "progress.json", progress)
        else:
            benchmark.tracker.track_termination(reason="exceeding_max_steps", msg=f"Reached {max_steps} action proposals.")

        benchmark.termination_evaluation()
        benchmark.tracker.save_tracking(str(output / "report.json"))
        progress["phase"] = "evaluation_saved"
        save_json(output / "progress.json", progress)
        print("MODEL_EPISODE_REPORT_SAVED", flush=True)
        try:
            views("99_final")
            progress["final_views_saved"] = True
        except Exception:
            progress["final_views_saved"] = False
            progress["final_render_exception"] = traceback.format_exc()
        save_json(output / "progress.json", progress)
    except Exception:
        progress["phase"] = "infrastructure_failed"
        progress["exception"] = traceback.format_exc()
        # Preserve the inference child's original exception; otherwise a long
        # simulator shutdown traceback obscures the actionable loading error.
        if "response_file" in locals() and response_file.is_file():
            failed_response = json.loads(response_file.read_text())
            if failed_response.get("error"):
                progress["inference_error"] = failed_response["error"]
                print("INFERENCE_ERROR:", failed_response["error"], flush=True)
        save_json(output / "progress.json", progress)
        if benchmark is not None:
            benchmark.tracker.save_tracking(str(output / "report_partial.json"))
        raise
    finally:
        if "og" in locals():
            (output / "cleanup_started.txt").write_text("og.shutdown()\n")
            print("SIMULATOR_CLEANUP_START", flush=True)
            og.shutdown()
            (output / "cleanup_completed.txt").write_text("clean shutdown\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--max-steps", type=int, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--scene", default="Rs_int")
    parser.add_argument("--prompt-setting", choices=("v1", "v3"), default="v1")
    args = parser.parse_args()
    assert 1 <= args.max_steps <= 100
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "progress.json").exists():
        raise RuntimeError("Refusing to overwrite a previous episode.")
    run_episode(args.repo.resolve(), args.output.resolve(), args.worker.resolve(), args.model_path.resolve(), args.max_steps, args.task, args.scene, args.prompt_setting)
