"""Compatibility preference without installing Python or touching shared packages."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from tools import python_selection as selection
from tools import runtime_check as runtime


def candidate(minor, ready=True):
    return dict(major=3, minor=minor, ready=ready,
                executable=str(Path(sys.executable).parent / f'python3.{minor}'))


class SelectionTests(unittest.TestCase):
    def test_prefer_working_315_then_314_then_another_installed_version(self):
        choices = [candidate(12), candidate(14), candidate(15)]
        self.assertEqual(selection.select_candidate(choices)['minor'], 15)
        choices[2]['ready'] = False
        self.assertEqual(selection.select_candidate(choices)['minor'], 14)
        choices[1]['ready'] = False
        self.assertEqual(selection.select_candidate(choices)['minor'], 12)
        choices[0]['ready'] = False
        self.assertEqual(selection.select_candidate(choices)['minor'], 14)
        self.assertIsNone(selection.select_candidate([candidate(9)]))
        self.assertEqual(selection.select_candidate([candidate(15, False)])['minor'], 15)

    def test_only_local_probe_no_package_or_interpreter_installation(self):
        data = candidate(14)
        with patch.object(selection.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(data))) as run:
            self.assertEqual(selection.probe(data['executable']), data)
            self.assertEqual(run.call_args.args[0][:2], [data['executable'], '-c'])
            self.assertEqual(run.call_args.kwargs['timeout'], 15)
            self.assertNotIn('pip', run.call_args.args[0][2])

    def test_probe_failures_are_skipped(self):
        failures = [OSError('missing'), subprocess.TimeoutExpired('python', 15)]
        for failure in failures:
            with patch.object(selection.subprocess, 'run', side_effect=failure):
                self.assertIsNone(selection.probe('/python'))
        for code, output in [(-6, ''), (1, ''), (0, 'garbage'), (0, '{}')]:
            with patch.object(selection.subprocess, 'run', return_value=subprocess.CompletedProcess([], code, output)):
                self.assertIsNone(selection.probe('/python'))

    def test_base_interpreter_is_rechecked_without_venv_packages(self):
        base = candidate(15, False)
        other = candidate(14)
        venv = str(Path(sys.executable).parent / 'app-venv-python')
        with patch.object(selection, 'installed_candidates', return_value=[venv, other['executable']]), \
             patch.object(selection, 'probe', side_effect=[dict(base, ready=True), base, other]) as probe:
            self.assertEqual(selection.select_python(), other['executable'])
            self.assertEqual(probe.call_args_list[1].args[0], base['executable'])

    def test_no_usable_python_is_an_error_not_an_installation(self):
        with patch.object(selection, 'installed_candidates', return_value=['/missing']), \
             patch.object(selection, 'probe', return_value=None):
            with self.assertRaises(RuntimeError):
                selection.select_python()

    @unittest.skipIf(os.name == 'nt', 'Windows selection is performed by PowerShell')
    def test_posix_delegates_once_preserving_arguments_without_repair(self):
        selected = candidate(14)['executable']
        with patch.object(sys, 'argv', ['runtime_check.py', '--no-repair']), \
             patch.dict(os.environ, {'SEMESTERLISTA_PYTHON_SELECTED': ''}), \
             patch('core.logging_setup.setup_logging'), \
             patch.object(runtime.logging, 'shutdown'), \
             patch.object(runtime, 'preferred_python', return_value=selected), \
             patch.object(runtime.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run, \
             patch.object(runtime, 'repair_environment') as repair:
            self.assertEqual(runtime.main(), 0)
            run.assert_called_once()
            command = run.call_args.args[0]
            self.assertEqual(command[0], selected)
            self.assertEqual(command[-1], '--no-repair')
            self.assertEqual(run.call_args.kwargs['env']['SEMESTERLISTA_PYTHON_SELECTED'], '1')
            repair.assert_not_called()
