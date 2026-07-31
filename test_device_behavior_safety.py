import json
import os
import tempfile
import unittest

import app


class DeviceBehaviorSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.keymap_path = os.path.join(self.tempdir.name, 'test.keymap')
        with open(self.keymap_path, 'w', encoding='utf-8') as f:
            f.write('/ { keymap { compatible = "zmk,keymap"; }; };\n')
        self.settings_path = os.path.join(self.tempdir.name, 'settings.json')
        with open(self.settings_path, 'w', encoding='utf-8') as f:
            json.dump({'keymap_path': self.keymap_path}, f)
        self.old_settings_file = app.SETTINGS_FILE
        app.SETTINGS_FILE = self.settings_path
        app.app.testing = True
        self.client = app.app.test_client()

    def tearDown(self):
        app.SETTINGS_FILE = self.old_settings_file
        self.tempdir.cleanup()

    def test_finds_unique_unresolved_device_behavior_placeholders(self):
        layers = [
            {
                'bindings': [
                    {'raw': '&kp A'},
                    {'raw': '&behavior_39 0 1'},
                    {'raw': '&behavior_42 0 458796'},
                    {'raw': '&behavior_39 1 2'},
                ]
            }
        ]

        self.assertEqual(
            app.find_unresolved_device_behaviors(layers),
            ['&behavior_39', '&behavior_42'],
        )

    def test_does_not_reject_named_behaviors(self):
        layers = [
            {
                'bindings': [
                    {'raw': '&zip_dyn_scale ZDS_SC ZDS_INC'},
                    {'raw': '&layer_overlay_secondary'},
                    {'raw': '&layer_overlay_secondary_space 0 SPACE'},
                ]
            }
        ]

        self.assertEqual(app.find_unresolved_device_behaviors(layers), [])

    def test_keymap_api_refuses_to_write_unresolved_device_behavior(self):
        with open(self.keymap_path, encoding='utf-8') as f:
            original = f.read()

        response = self.client.post(
            '/api/keymap',
            json={
                'layers': [
                    {
                        'name': 'default_layer',
                        'bindings': [{'raw': '&behavior_39 0 1'}],
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('&behavior_39', response.get_json()['error'])
        with open(self.keymap_path, encoding='utf-8') as f:
            self.assertEqual(f.read(), original)


if __name__ == '__main__':
    unittest.main()
