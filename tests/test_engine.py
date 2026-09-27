import copy
import json
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from shiftcore.backends import MacBackend
from shiftcore.config import DEFAULT_CONFIG, input_value, load_config, save_config, shortcut_spec, other_host
from shiftcore.engine import Display, resolve, switch_all


class FakeBackend:
    def __init__(self, displays=None, fail=None):
        self.displays = displays if displays is not None else [
            Display('lg', 'LG ULTRAFINE'), Display('alien', 'AW2725QF'), Display('asus', 'VG27AQ3A')]
        self.writes = []
        self.fail = fail
        self.open = False

    @contextmanager
    def session(self):
        self.open = True
        try:
            yield self.displays
        finally:
            self.open = False

    def check_protocol(self, protocol):
        pass

    def write(self, display, value, protocol):
        assert self.open
        self.writes.append((display.identifier, value, protocol))
        if display.identifier == self.fail:
            raise RuntimeError('Disconnected during handoff')
        # Emulate topology change after a switch; the entire plan must already be resolved.
        self.displays[:] = [d for d in self.displays if d.identifier != display.identifier]

    def probe(self, display):
        display.current_input = 15
        display.detail = '当前输入 0x0f'


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        for profile in self.config['displays']:
            profile['enabled'] = True

    def test_windows_mapping_survives_reorder_and_topology_change(self):
        backend = FakeBackend()
        results = switch_all(self.config, backend, 'Darwin', 'windows')
        self.assertEqual([('asus', 18, 'standard'), ('alien', 15, 'standard'), ('lg', 208, 'lg-alt')], backend.writes)
        self.assertTrue(all(r.status == 'sent' for r in results))
        self.assertFalse(backend.open)

    def test_uncalibrated_lg_does_not_write_guessed_value(self):
        self.config['displays'][2]['mac_input'] = ''
        backend = FakeBackend()
        results = switch_all(self.config, backend, 'Windows', 'mac')
        self.assertEqual([('asus', 17, 'standard'), ('alien', 17, 'standard')], backend.writes)
        self.assertEqual(1, sum(r.status == 'failed' for r in results))

    def test_one_failure_does_not_skip_remaining_displays(self):
        backend = FakeBackend(fail='asus')
        results = switch_all(self.config, backend, 'Darwin', 'windows')
        self.assertEqual(3, len(backend.writes))
        self.assertEqual(['failed', 'sent', 'sent'], [r.status for r in results])

    def test_dry_run_never_writes(self):
        backend = FakeBackend()
        results = switch_all(self.config, backend, 'Windows', 'windows', dry_run=True)
        self.assertFalse(backend.writes)
        self.assertTrue(all(r.status == 'planned' for r in results))

    def test_no_displays_not_success(self):
        results = switch_all(self.config, FakeBackend([]), 'Windows', 'mac')
        self.assertTrue(all(r.status == 'failed' for r in results))

    def test_saved_id_missing_never_falls_back_to_same_model(self):
        profile = self.config['displays'][0]
        profile['ids']['Windows'] = 'unplugged'
        with self.assertRaises(ValueError):
            resolve(profile, FakeBackend().displays, 'Windows')

    def test_duplicate_models_require_binding(self):
        displays = [Display('one', 'VG27AQ3A'), Display('two', 'VG27AQ3A')]
        with self.assertRaises(ValueError):
            resolve(self.config['displays'][0], displays, 'Windows')
        self.config['displays'][0]['ids']['Windows'] = 'two'
        self.assertEqual('two', resolve(self.config['displays'][0], displays, 'Windows').identifier)

    def test_overlap_does_not_write_same_display_twice(self):
        self.config['displays'][1]['match'] = ['VG27AQ3A']
        backend = FakeBackend()
        results = switch_all(self.config, backend, 'Windows', 'windows')
        self.assertEqual([('lg', 208, 'lg-alt')], backend.writes)
        self.assertEqual(2, sum(r.status == 'failed' for r in results))

    def test_disabled_display_is_excluded(self):
        self.config['displays'][0]['enabled'] = False
        backend = FakeBackend()
        switch_all(self.config, backend, 'Windows', 'windows')
        self.assertNotIn('asus', [w[0] for w in backend.writes])

    def test_shortcut_direction_and_syntax(self):
        self.assertEqual('mac', other_host('Windows'))
        self.assertEqual('windows', other_host('Darwin'))
        self.assertEqual('<ctrl>+<alt>+<shift>+d', shortcut_spec('ctrl+alt+shift+d'))
        for value in ('ctrl+d+d', 'd', 'ctrl++d', 'alt+💡'):
            with self.assertRaises(ValueError):
                shortcut_spec(value)

    def test_input_validation(self):
        self.assertEqual(18, input_value('0x12'))
        self.assertEqual(18, input_value('18'))
        for value in ('', '-1', '0', '0x100', 'hello'):
            with self.assertRaises(ValueError):
                input_value(value)

    def test_config_roundtrip_and_reject_corruption_without_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            save_config(self.config, path)
            self.assertEqual(self.config, load_config(path))
            # Test fixture, not application mutation.
            path.write_text('{broken', encoding='utf-8')
            with self.assertRaises(json.JSONDecodeError):
                load_config(path)
            self.assertEqual('{broken', path.read_text(encoding='utf-8'))

    def test_legacy_global_config_not_silently_applied(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            path.write_text('{"mac_input":"0x11"}', encoding='utf-8')
            with self.assertRaises(ValueError):
                load_config(path)


class MacTests(unittest.TestCase):
    @patch.object(MacBackend, 'command')
    def test_aw_repeated_input_bytes_are_model_specific(self, command):
        backend = MacBackend('/m1ddc')
        for raw, expected in [('4369', 17), ('3855', 15), ('4626', 18), ('17', 17)]:
            command.return_value = raw
            display = Display('id', 'AW2725QF')
            backend.probe(display)
            self.assertEqual(expected, display.current_input)
        for name, raw in [('LG ULTRAFINE', '4369'), ('AW2725QF', '2809'),
                          ('VG27AQ3A', '0'), ('AW2725QF', '4370')]:
            command.return_value = raw
            display = Display('id', name, 17)
            backend.probe(display)
            self.assertIsNone(display.current_input)

    @patch.object(MacBackend, 'command')
    def test_null_reply_clears_previous_value(self, command):
        command.side_effect = RuntimeError('DDC null reply: display did not answer the VCP query.')
        display = Display('id', 'LG ULTRAFINE', 16)
        MacBackend('/m1ddc').probe(display)
        self.assertIsNone(display.current_input)
        self.assertIn('空应答', display.detail)

    @patch.object(MacBackend, 'command', return_value='15')
    def test_lg_standard_read_is_not_claimed_to_be_calibrated(self, command):
        display = Display('id', 'LG ULTRAFINE')
        MacBackend('/m1ddc').probe(display)
        self.assertEqual(15, display.current_input)
        self.assertIn('不能据此校准', display.detail)

    def test_parse_uuid_and_preserve_name(self):
        found = MacBackend.parse_displays('[1] LG ULTRAFINE (12345678-1234-1234-1234-123456789abc)\n[2] AW2725QF (98765432-1234-1234-1234-123456789abc)')
        self.assertEqual('LG ULTRAFINE', found[0].name)
        self.assertEqual('98765432-1234-1234-1234-123456789abc', found[1].identifier)
        with self.assertRaises(RuntimeError):
            MacBackend.parse_displays('Unsupported output format')

    @patch('shiftcore.backends.subprocess.run')
    def test_native_helper_uses_uuid_decimal_and_no_shell(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, 'Writing 208', '')
        backend = MacBackend('/Applications/Tools/m1ddc')
        backend.write(Display('display-uuid', 'LG'), 0xd0, 'lg-alt')
        self.assertEqual(['/Applications/Tools/m1ddc', 'display', 'display-uuid', 'set', 'input-alt', '208'], run.call_args.args[0])
        self.assertNotIn('shell', run.call_args.kwargs)
        self.assertEqual(12, run.call_args.kwargs['timeout'])

    @patch('shiftcore.backends.subprocess.run')
    def test_helper_failure_not_reported_as_success(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, 'DDC communication failure', '')
        with self.assertRaisesRegex(RuntimeError, 'DDC communication'):
            MacBackend('/m1ddc').write(Display('id', 'ASUS'), 17, 'standard')

    @patch('shiftcore.backends.subprocess.run')
    def test_helper_timeout_becomes_actionable_error(self, run):
        run.side_effect = subprocess.TimeoutExpired('m1ddc', 12)
        with self.assertRaisesRegex(RuntimeError, '超时'):
            MacBackend('/m1ddc').command('display', 'list')


if __name__ == '__main__':
    unittest.main()
