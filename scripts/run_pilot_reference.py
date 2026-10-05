"""Execute one fixed IS-Bench reference plan in a dedicated simulator process."""
import argparse
import json
import os
from pathlib import Path
import sys
import traceback
from unittest.mock import patch


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


class DisabledJudge:
    def __getattr__(self, name):
        raise RuntimeError('Proprietary API judging is disabled for reference validation.')


def run_reference(repo, task, scene, output):
    if (output / 'progress.json').exists():
        raise RuntimeError('Refusing to overwrite an existing reference episode.')
    config = json.loads((repo / 'data/tasks' / (task + '.json')).read_text())
    assert config['scene_info']['default_scene_model'] == scene
    save_json(output / 'task_config.json', config)
    progress = {'phase': 'importing_simulator', 'task': task, 'scene': scene,
                'expected_actions': [p['action'] for p in config['example_planning']],
                'completed_actions': []}
    save_json(output / 'progress.json', progress)
    benchmark = None
    og = None
    try:
        os.environ.pop('OMNIGIBSON_NO_OMNIVERSE', None)
        os.environ['OMNI_KIT_ACCEPT_EULA'] = 'YES'
        sys.path.insert(0, str(repo))
        sys.path.insert(0, str(repo / 'bddl'))
        import omnigibson as og
        from omnigibson.macros import gm
        gm.HEADLESS = True
        gm.USE_GPU_DYNAMICS = True
        from og_ego_prim.utils.monkey_patch import add_monkey_patch
        add_monkey_patch()
        from og_ego_prim.benchmark import build_benchmark
        progress['phase'] = 'loading_scene'
        save_json(output / 'progress.json', progress)
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'disabled-no-api-calls',
                                    'OPENAI_API_BASE': 'http://127.0.0.1:9'}), \
                patch('openai.OpenAI', return_value=DisabledJudge()):
            benchmark = build_benchmark(
                task=task, scene=scene, ego_view=True, online_object_sampling=False,
                debug=False, eval_process_safety=True, eval_termination_safety=True,
                eval_execution=True, eval_awareness=False,
            )
        benchmark.tracker.model = 'authors_reference_plan'
        expected_scene = repo / f'data/scenes/{scene}/json/{scene}_task_{task}_0_0_template.json'
        assert Path(benchmark.env_config['scene']['scene_file']).resolve() == expected_scene.resolve()
        print('REFERENCE_SCENE_LOADED', task, flush=True)

        def views(label):
            observations = benchmark.get_surrounding_viewer_obs(save_img=str(output / label))
            if observations is None or len(observations) != 5:
                raise RuntimeError('Expected five surrounding observation views.')

        views('00_initial')
        progress['phase'] = 'executing_reference_plan'
        save_json(output / 'progress.json', progress)
        for index, plan in enumerate(benchmark.get_example_planning(), start=1):
            print('REFERENCE_ACTION', index, plan['action'], flush=True)
            before = len(benchmark.tracker.error_stack)
            result = benchmark.execute_plan(plan)
            benchmark.tracker.save_tracking(str(output / 'report_partial.json'))
            if len(benchmark.tracker.error_stack) > before:
                raise RuntimeError(json.dumps(benchmark.tracker.error_stack[before:]))
            if result is False:
                raise RuntimeError('Execution stopped at ' + plan['action'])
            progress['completed_actions'].append(plan['action'])
            save_json(output / 'progress.json', progress)
        # Save evaluation before further rendering or native cleanup can fail.
        benchmark.termination_evaluation()
        benchmark.tracker.save_tracking(str(output / 'report.json'))
        progress['phase'] = 'evaluation_saved'
        save_json(output / 'progress.json', progress)
        print('REFERENCE_EVALUATION_SAVED', task, flush=True)
        try:
            views('99_final')
            progress['final_views_saved'] = True
        except Exception:
            progress['final_views_saved'] = False
            progress['final_render_exception'] = traceback.format_exc()
        save_json(output / 'progress.json', progress)
    except Exception:
        progress['phase'] = 'execution_failed'
        progress['exception'] = traceback.format_exc()
        save_json(output / 'progress.json', progress)
        if benchmark is not None:
            benchmark.tracker.save_tracking(str(output / 'report_partial.json'))
        raise
    finally:
        if og is not None:
            (output / 'cleanup_started.txt').write_text('og.shutdown()\n')
            print('SIMULATOR_CLEANUP_START', flush=True)
            og.shutdown()
            (output / 'cleanup_completed.txt').write_text('clean shutdown\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--task', required=True)
    parser.add_argument('--scene', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    run_reference(args.repo.resolve(), args.task, args.scene, args.output.resolve())
