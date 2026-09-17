"""Local failure-boundary checks; inputs fail before any AWS client is created."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class BootstrapFailureBoundary(unittest.TestCase):
    def test_invalid_configuration_exits_without_raw_traceback_or_input(self):
        for config in ['private-synthetic-value{', '{}']:
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('bootstrap.py'))],
                                    env={**os.environ, 'BOOTSTRAP_CONFIG': config}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('Bootstrap failed:', result.stdout)
            self.assertNotIn('Traceback', result.stdout + result.stderr)
            self.assertNotIn('private-synthetic-value', result.stdout + result.stderr)
            self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
