"""Exercise low-memory startup and container ownership without touching Docker."""
import os
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LifecycleTests(unittest.TestCase):
    def test_guard_stops_only_its_labeled_container_below_floor(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'logs').mkdir()
            env = {'KANANA_CONTAINER': 'isolated-test', 'KANANA_MIN_FREE_GIB': '8', 'KANANA_HOME': directory}
            inspected = subprocess.CompletedProcess([], 0, 'true kanana-dgx-sparks\n', '')
            stopped = subprocess.CompletedProcess([], 0)
            with patch.dict(os.environ, env), patch('pathlib.Path.read_text', return_value='MemAvailable: 1024 kB\n'), \
                    patch('subprocess.run', side_effect=[inspected, stopped]) as process:
                runpy.run_path(str(ROOT / 'scripts/memory_guard.py'), run_name='__main__')
            self.assertEqual(process.call_args_list[1].args[0], ['docker', 'stop', '-t', '2', 'isolated-test'])
            self.assertTrue((Path(directory) / 'logs/memory-abort.json').exists())

    def test_insufficient_memory_refuses_to_start(self):
        result = subprocess.run(['python3', str(ROOT / 'scripts/preflight.py')],
                                env={**os.environ, 'KANANA_MIN_START_GIB': '1000000'},
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Other models are not stopped automatically', result.stderr)

    def test_foreign_container_is_not_stopped_or_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            docker = work / 'docker'
            docker.write_text('#!/bin/sh\n'
                              'echo "$*" >> "$DOCKER_CALLS"\n'
                              'case "$*" in\n'
                              '  "container inspect "*) exit 0;;\n'
                              '  "inspect "*) echo foreign-deployment; exit 0;;\n'
                              '  *) exit 99;;\n'
                              'esac\n')
            docker.chmod(0o755)
            env = {**os.environ, 'PATH': directory + ':' + os.environ['PATH'],
                   'KANANA_HOME': str(work / 'data'), 'DOCKER_CALLS': str(work / 'calls')}
            for script in ('start.sh', 'stop.sh'):
                result = subprocess.run(['bash', str(ROOT / script)], env=env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
            calls = (work / 'calls').read_text().splitlines()
            self.assertTrue(calls)
            self.assertFalse(any(line.startswith(('stop ', 'rm ', 'run ')) for line in calls))


if __name__ == '__main__':
    unittest.main()
