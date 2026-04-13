import os
import tempfile
import unittest
from unittest import mock

import app as editor


MINIMAL_KEYMAP = """/ {
    keymap {
        compatible = "zmk,keymap";

        default_layer {
            bindings = <&kp A>;
        };
    };
};
"""


class TDModuleInstallTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = self.tempdir.name
        os.makedirs(os.path.join(self.root, 'config'))
        os.makedirs(os.path.join(self.root, 'boards'))
        os.makedirs(os.path.join(self.root, 'zephyr'))

        self.keymap_path = os.path.join(self.root, 'config', 'lalapadgen2.keymap')
        with open(self.keymap_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(MINIMAL_KEYMAP)

        self.settings_path = os.path.join(self.root, 'settings.json')
        self._old_settings_file = editor.SETTINGS_FILE
        editor.SETTINGS_FILE = self.settings_path
        self._write_settings()

        editor.app.testing = True
        self.client = editor.app.test_client()

    def tearDown(self):
        editor.SETTINGS_FILE = self._old_settings_file
        self.tempdir.cleanup()

    def _write_settings(self):
        settings = editor.make_default_settings()
        settings.update({
            'firmware_folder': self.root,
            'keymap_path': self.keymap_path,
            'main_conf_path': os.path.join(self.root, 'config', 'lalapadgen2.conf'),
            'left_conf_path': os.path.join(self.root, 'config', 'boards', 'shields', 'lalapadgen2', 'lalapadgen2_left.conf'),
            'right_conf_path': os.path.join(self.root, 'config', 'boards', 'shields', 'lalapadgen2', 'lalapadgen2_right.conf'),
            'keyboard_name': 'lalapadgen2',
        })
        editor.save_settings_file(settings)

    def _active_td_defs(self):
        return editor.normalize_td_definitions([
            {
                'single_tap': '&kp J',
                'single_hold': '&kp LEFT_CONTROL',
                'double_tap': '&kp Z',
                'tapping_term': 200,
            }
        ])

    def _save_keymap(self, td_definitions):
        return self.client.post('/api/keymap', json={
            'layers': [],
            'combos': [],
            'conditional_layers': [],
            'macro_definitions': [],
            'td_definitions': td_definitions,
        })

    def test_td_not_used_skips_module_install(self):
        response = self._save_keymap(editor.normalize_td_definitions([]))
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['td_module'], 'not_needed')
        self.assertFalse(os.path.exists(os.path.join(self.root, editor.TD_MODULE_NAME)))
        self.assertFalse(os.path.exists(os.path.join(self.root, 'zephyr', 'module.yml')))

    def test_initial_td_save_installs_module(self):
        response = self._save_keymap(self._active_td_defs())
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['td_module'], 'installed')

        for src, rel in editor._iter_td_module_template_files():
            dest = os.path.join(self.root, editor.TD_MODULE_NAME, rel)
            self.assertTrue(os.path.exists(dest), dest)
            self.assertEqual(
                editor._normalize_text_for_compare(editor._read_text_file(dest)),
                editor._normalize_text_for_compare(editor._read_text_file(src)),
            )

        module_yml_path = os.path.join(self.root, 'zephyr', 'module.yml')
        module_yml = editor._read_text_file(module_yml_path)
        self.assertIn('board_root: .', module_yml)
        self.assertIn(f'dts_root: {editor.TD_MODULE_NAME}', module_yml)
        self.assertIn(f'cmake: {editor.TD_MODULE_NAME}', module_yml)
        self.assertIn(f'kconfig: {editor.TD_MODULE_NAME}/Kconfig', module_yml)

    def test_second_td_save_reports_already_present(self):
        first = self._save_keymap(self._active_td_defs())
        self.assertEqual(first.status_code, 200)

        second = self._save_keymap(self._active_td_defs())
        payload = second.get_json()

        self.assertEqual(second.status_code, 200)
        self.assertEqual(payload['td_module'], 'already_present')

    def test_conflicting_module_file_blocks_keymap_save(self):
        module_dir = os.path.join(self.root, editor.TD_MODULE_NAME)
        os.makedirs(module_dir, exist_ok=True)
        conflicting_file = os.path.join(module_dir, 'Kconfig')
        with open(conflicting_file, 'w', encoding='utf-8', newline='\n') as f:
            f.write('different content\n')

        before = editor._read_text_file(self.keymap_path)
        response = self._save_keymap(self._active_td_defs())
        payload = response.get_json()
        after = editor._read_text_file(self.keymap_path)

        self.assertEqual(response.status_code, 409)
        self.assertIn(conflicting_file, payload['error'])
        self.assertEqual(after, before)

    def test_conflicting_module_yml_blocks_keymap_save(self):
        module_yml_path = os.path.join(self.root, 'zephyr', 'module.yml')
        with open(module_yml_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(
                'build:\n'
                '  settings:\n'
                '    board_root: .\n'
                '    dts_root: something_else\n'
            )

        before = editor._read_text_file(self.keymap_path)
        response = self._save_keymap(self._active_td_defs())
        payload = response.get_json()
        after = editor._read_text_file(self.keymap_path)

        self.assertEqual(response.status_code, 409)
        self.assertIn(module_yml_path, payload['error'])
        self.assertEqual(after, before)

    def test_wsl_write_text_file_uses_mkdir_and_cp(self):
        unc_path = r'\\wsl$\Ubuntu\home\tester\demo\file.txt'
        completed = mock.Mock(returncode=0, stderr='')

        with mock.patch('app.subprocess.run', return_value=completed) as run:
            editor.write_text_file(unc_path, 'hello')

        self.assertEqual(run.call_count, 2)
        mkdir_call = run.call_args_list[0]
        cp_call = run.call_args_list[1]
        self.assertEqual(mkdir_call.args[0], ['wsl', '-u', 'root', '-e', 'mkdir', '-p', '/home/tester/demo'])
        self.assertEqual(cp_call.args[0][-1], '/home/tester/demo/file.txt')
        self.assertEqual(cp_call.args[0][:4], ['wsl', '-u', 'root', '-e'])


if __name__ == '__main__':
    unittest.main()
