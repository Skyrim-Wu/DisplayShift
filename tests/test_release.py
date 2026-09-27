import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shiftcore.backends import MacBackend
from shiftcore.config import DEFAULT_CONFIG, load_config, save_config
from shiftcore.engine import switch_all
from test_engine import FakeBackend


class ReleaseTests(unittest.TestCase):
    def test_fresh_install_switches_all_three_with_verified_lg_protocol(self):
        backend = FakeBackend()
        results = switch_all(copy.deepcopy(DEFAULT_CONFIG), backend, 'Windows', 'mac')
        self.assertEqual([('asus', 17, 'standard'), ('alien', 17, 'standard'), ('lg', 209, 'lg-alt')], backend.writes)
        self.assertTrue(all(result.status == 'sent' for result in results))

    def test_existing_user_choices_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            config = copy.deepcopy(DEFAULT_CONFIG)
            config['displays'][0]['enabled'] = False
            save_config(config, path)
            self.assertEqual(config, load_config(path))

    def test_bundle_finds_its_helper_even_without_path(self):
        with tempfile.TemporaryDirectory() as folder:
            helper = Path(folder) / 'bin' / 'm1ddc'
            helper.parent.mkdir()
            helper.touch()
            with patch('shiftcore.backends.sys.frozen', True, create=True), \
                    patch('shiftcore.backends.sys._MEIPASS', folder, create=True), \
                    patch('shiftcore.backends.shutil.which', return_value='/old/m1ddc'):
                self.assertEqual(str(helper), MacBackend().executable)
                self.assertEqual('/custom/m1ddc', MacBackend('/custom/m1ddc').executable)
