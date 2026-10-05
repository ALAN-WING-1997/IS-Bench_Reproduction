"""Summarize reference validation independently of native simulator cleanup."""
import json
from pathlib import Path


def summarize(output, config, returncode, timed_out=False):
    output = Path(output)
    read_errors = []
    def load(name):
        path = output / name
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            read_errors.append({'file': name, 'error': str(exc)})
            return {}
    report, progress = load('report.json'), load('progress.json')
    goals = config['evaluation_goal_conditions']
    expected_process = len(goals.get('process_safety_goal_condition', []))
    expected_term = len(goals.get('termination_safety_goal_condition', []))
    process = report.get('process_safety_goal_condition', [])
    term = report.get('termination_safety_goal_condition', [])
    all_safety = process + term
    expected = [p['action'] for p in config['example_planning']]
    actual = [p['action'] for p in report.get('plans', [])]
    def norm(actions):
        normalized = [a.lower().replace(' ', '') for a in actions]
        return ['done' if a in ('done', 'done()') else a for a in normalized]
    checks = {
        'evaluation_finished': progress.get('phase') == 'evaluation_saved',
        'all_reference_actions_recorded': norm(actual) == norm(expected)
            and norm(progress.get('completed_actions', [])) == norm(expected),
        'terminated_with_done': (report.get('termination') or {}).get('reason') == 'done',
        'no_action_errors': 'error_stack' in report and not report['error_stack'],
        'task_goal_satisfied': report.get('execution_goal_condition', {}).get('eval') is True,
        'safety_check_coverage': len(process) == expected_process and len(term) == expected_term,
        'all_annotated_safety_checks_passed': all(g.get('eval') is True for g in all_safety),
        'initial_views_saved': all((output / '00_initial' / f'obs_{i}.png').is_file() for i in range(5)),
    }
    passed = all(checks.values())
    safety_status = 'no_predicate_checks' if expected_process + expected_term == 0 else (
        'passed' if checks['safety_check_coverage'] and checks['all_annotated_safety_checks_passed'] else 'failed_or_incomplete')
    return {
        'task': config['task_info']['task_name'],
        'scene': config['scene_info']['default_scene_model'],
        'reference_checks_passed': passed, 'checks': checks,
        'task_completed': report.get('execution_goal_condition', {}).get('eval'),
        'safety_status': safety_status,
        'expected_safety_checks': expected_process + expected_term,
        'recorded_safety_checks': len(all_safety),
        'passed_safety_checks': sum(g.get('eval') is True for g in all_safety),
        'action_errors': report.get('error_stack', load('report_partial.json').get('error_stack', [])),
        'completed_reference_actions': progress.get('completed_actions', []),
        'expected_action_count': len(expected),
        'process_returncode': returncode, 'timed_out': timed_out,
        'clean_shutdown': returncode == 0 and (output / 'cleanup_completed.txt').is_file(),
        'segmentation_fault_after_saved_evaluation': checks['evaluation_finished']
            and (output / 'cleanup_started.txt').is_file()
            and not (output / 'cleanup_completed.txt').is_file()
            and returncode in (-11, 139),
        'last_phase': progress.get('phase', 'no_progress'),
        'exception': progress.get('exception'),
        'report_read_errors': read_errors,
        'final_views_saved': progress.get('final_views_saved', False),
        'scope': 'fixed reference-plan environment validation; no model score or awareness judge',
    }
