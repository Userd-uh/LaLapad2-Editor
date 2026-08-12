import json
import os
import tempfile
import unittest
from unittest import mock

import app


KCONFIG_LEFT = '''if SHIELD_LALAPADGEN2_LEFT

config ZMK_KEYBOARD_NAME
    default "LalapadGen2"

config ZMK_SPLIT_ROLE_CENTRAL
    default y

endif

if SHIELD_LALAPADGEN2_LEFT || SHIELD_LALAPADGEN2_RIGHT
config ZMK_SPLIT
    default y
endif
'''

BUILD_LEFT = '''---
include:
  - board: seeeduino_xiao_ble
    shield: lalapadgen2_right rgbled_adapter
  - board: seeeduino_xiao_ble
    shield: lalapadgen2_left rgbled_adapter
    snippet: studio-rpc-usb-uart
  - board: seeeduino_xiao_ble
    shield: settings_reset
'''

LEFT_OVERLAY_CENTRAL = '''#include "lalapadgen2.dtsi"

&trackpad_listener_L {
    status = "okay";
    device = <&iqs9151>;
};

&trackpad_listener_R {
    status = "okay";
};
'''

RIGHT_OVERLAY_PERIPHERAL = '''#include "lalapadgen2.dtsi"

&trackpad_split_R {
    status = "okay";
    device = <&iqs9151>;
};

&trackpad_split_L {
    status = "disabled";
};
'''


class PrimarySwitchTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = self.tempdir.name
        self.config_dir = os.path.join(self.root, 'config')
        self.shield_dir = os.path.join(self.config_dir, 'boards', 'shields', 'lalapadgen2')
        os.makedirs(self.shield_dir)
        with open(os.path.join(self.config_dir, 'lalapadgen2.keymap'), 'w', encoding='utf-8') as f:
            f.write('/ { keymap { compatible = "zmk,keymap"; }; };\n')
        self.kconfig_path = os.path.join(self.shield_dir, 'Kconfig.defconfig')
        self.build_path = os.path.join(self.root, 'build.yaml')
        self.left_overlay_path = os.path.join(self.shield_dir, 'lalapadgen2_left.overlay')
        self.right_overlay_path = os.path.join(self.shield_dir, 'lalapadgen2_right.overlay')
        with open(self.kconfig_path, 'w', encoding='utf-8') as f:
            f.write(KCONFIG_LEFT)
        with open(self.build_path, 'w', encoding='utf-8') as f:
            f.write(BUILD_LEFT)
        with open(self.left_overlay_path, 'w', encoding='utf-8') as f:
            f.write(LEFT_OVERLAY_CENTRAL)
        with open(self.right_overlay_path, 'w', encoding='utf-8') as f:
            f.write(RIGHT_OVERLAY_PERIPHERAL)
        self.settings_path = os.path.join(self.root, 'settings.json')
        with open(self.settings_path, 'w', encoding='utf-8') as f:
            json.dump({'firmware_folder': self.root, 'keyboard_name': 'lalapadgen2'}, f)
        self.old_settings_file = app.SETTINGS_FILE
        app.SETTINGS_FILE = self.settings_path
        app.app.testing = True
        self.client = app.app.test_client()

    def tearDown(self):
        app.SETTINGS_FILE = self.old_settings_file
        self.tempdir.cleanup()

    def test_detects_left_primary_and_studio_target(self):
        response = self.client.get('/api/firmware/primary')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['primary'], 'left')

    def test_switch_to_right_moves_central_and_studio_together(self):
        response = self.client.post('/api/firmware/primary', json={'primary': 'right'})
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result['changed'])
        self.assertEqual(result['previous_primary'], 'left')
        self.assertEqual(result['primary'], 'right')
        self.assertEqual(len(result['instructions']), 9)
        self.assertIn('left/right trackpad overlayを一括更新', result['instructions'][0])
        self.assertIn('settings_reset / right / left UF2を生成', result['instructions'][0])
        self.assertIn('settings_reset UF2 を物理的な右側へ書き込み', result['instructions'][1])
        self.assertIn('右側へ接続', result['instructions'][7])
        self.assertIn('RGBを含む永続設定を消去', result['instructions'][8])
        with open(self.kconfig_path, encoding='utf-8') as f:
            self.assertIn('if SHIELD_LALAPADGEN2_RIGHT', f.read())
        with open(self.build_path, encoding='utf-8') as f:
            build = f.read()
        right_entry = build.split('  - board: seeeduino_xiao_ble')[1]
        left_entry = build.split('  - board: seeeduino_xiao_ble')[2]
        self.assertIn('snippet: studio-rpc-usb-uart', right_entry)
        self.assertNotIn('snippet: studio-rpc-usb-uart', left_entry)
        with open(self.right_overlay_path, encoding='utf-8') as f:
            right_overlay = f.read()
        with open(self.left_overlay_path, encoding='utf-8') as f:
            left_overlay = f.read()
        self.assertIn('&trackpad_listener_R', right_overlay)
        self.assertIn('device = <&iqs9151>;', right_overlay)
        self.assertIn('&trackpad_listener_L', right_overlay)
        self.assertIn('&trackpad_split_L', left_overlay)
        self.assertIn('device = <&iqs9151>;', left_overlay)
        self.assertIn('&trackpad_split_R', left_overlay)

    def test_reapplying_current_primary_is_idempotent(self):
        self.client.post('/api/firmware/primary', json={'primary': 'right'})
        originals = {}
        for path in (self.kconfig_path, self.build_path, self.left_overlay_path, self.right_overlay_path):
            with open(path, encoding='utf-8') as f:
                originals[path] = f.read()
        response = self.client.post('/api/firmware/primary', json={'primary': 'right'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()['changed'])
        for path, before in originals.items():
            with open(path, encoding='utf-8') as f:
                self.assertEqual(f.read(), before)

    def test_switch_back_to_left_restores_the_original_overlay_roles(self):
        first = self.client.post('/api/firmware/primary', json={'primary': 'right'})
        self.assertEqual(first.status_code, 200)
        response = self.client.post('/api/firmware/primary', json={'primary': 'left'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['changed'])
        with open(self.kconfig_path, encoding='utf-8') as f:
            self.assertIn('if SHIELD_LALAPADGEN2_LEFT', f.read())
        with open(self.build_path, encoding='utf-8') as f:
            build = f.read()
        right_entry = build.split('  - board: seeeduino_xiao_ble')[1]
        left_entry = build.split('  - board: seeeduino_xiao_ble')[2]
        self.assertNotIn('snippet: studio-rpc-usb-uart', right_entry)
        self.assertIn('snippet: studio-rpc-usb-uart', left_entry)
        with open(self.left_overlay_path, encoding='utf-8') as f:
            left_overlay = f.read()
        with open(self.right_overlay_path, encoding='utf-8') as f:
            right_overlay = f.read()
        self.assertIn('&trackpad_listener_L', left_overlay)
        self.assertIn('device = <&iqs9151>;', left_overlay)
        self.assertIn('&trackpad_listener_R', left_overlay)
        self.assertIn('&trackpad_split_R', right_overlay)
        self.assertIn('device = <&iqs9151>;', right_overlay)
        self.assertIn('&trackpad_split_L', right_overlay)

    def test_invalid_build_is_rejected_without_partially_changing_kconfig(self):
        with open(self.build_path, 'w', encoding='utf-8') as f:
            f.write(BUILD_LEFT.replace('    snippet: studio-rpc-usb-uart\n', ''))
        with open(self.kconfig_path, encoding='utf-8') as f:
            before = f.read()
        response = self.client.post('/api/firmware/primary', json={'primary': 'right'})
        self.assertEqual(response.status_code, 400)
        with open(self.kconfig_path, encoding='utf-8') as f:
            self.assertEqual(f.read(), before)

    def test_invalid_overlay_is_rejected_without_changing_any_file(self):
        with open(self.right_overlay_path, 'w', encoding='utf-8') as f:
            f.write(RIGHT_OVERLAY_PERIPHERAL.replace('device = <&iqs9151>;', 'input = <&iqs9151>;'))
        originals = {}
        for path in (self.kconfig_path, self.build_path, self.left_overlay_path, self.right_overlay_path):
            with open(path, encoding='utf-8') as f:
                originals[path] = f.read()
        response = self.client.post('/api/firmware/primary', json={'primary': 'right'})
        self.assertEqual(response.status_code, 400)
        for path, before in originals.items():
            with open(path, encoding='utf-8') as f:
                self.assertEqual(f.read(), before)

    def test_replace_failure_rolls_back_all_four_files(self):
        originals = {}
        for path in (self.kconfig_path, self.build_path, self.left_overlay_path, self.right_overlay_path):
            with open(path, encoding='utf-8') as f:
                originals[path] = f.read()
        real_replace = os.replace
        call_count = 0

        def fail_second_replace(source, destination):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise OSError('simulated replace failure')
            return real_replace(source, destination)

        with mock.patch.object(app.os, 'replace', side_effect=fail_second_replace):
            response = self.client.post('/api/firmware/primary', json={'primary': 'right'})
        self.assertEqual(response.status_code, 500)
        for path, before in originals.items():
            with open(path, encoding='utf-8') as f:
                self.assertEqual(f.read(), before)


if __name__ == '__main__':
    unittest.main()
