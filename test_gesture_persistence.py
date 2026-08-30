from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app


class GesturePersistenceTests(unittest.TestCase):
    def test_mode_payload_persists_and_reads_back_per_side(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = {f'{side}_conf_path': str(Path(folder) / f'{side}.conf') for side in ('left', 'right')}
            for path in settings.values():
                Path(path).write_text('CONFIG_INPUT_IQS9151_1F_TAP_ENABLE=y\n')
            with patch.object(app, 'load_settings', return_value=settings):
                client = app.app.test_client()
                for side, modes in [('left', [0,1,2,1]), ('right', [2,0,1,2])]:
                    keys = [f'CONFIG_INPUT_IQS9151_{f}F_{axis}_MODE' for f in (2,3) for axis in ('HORIZONTAL','VERTICAL')]
                    payload = dict(zip(keys, map(str, modes)))
                    self.assertEqual(client.post(f'/api/config/{side}', json={'config': payload}).status_code, 200)
                    readback = client.get(f'/api/config/{side}').json['config']
                    self.assertEqual(readback['CONFIG_INPUT_IQS9151_1F_TAP_ENABLE'], 'y')
                    for key, value in payload.items():
                        self.assertEqual(readback[key], value)
                self.assertEqual(client.get('/api/config/left').json['config'][keys[0]], '0')

    def test_all_76_bindings_survive_serialization(self):
        bindings = [{'raw': f'&kp {i}'} for i in range(76)]
        output = app.format_bindings(bindings)
        import re
        self.assertEqual(re.findall(r'&kp \d+', output), [b['raw'] for b in bindings])
        self.assertEqual(len(re.findall(r'&kp \d+', app.format_bindings(bindings[:68]))), 68)
        with self.assertRaises(ValueError):
            app.format_bindings(bindings + [{'raw': '&trans'}])
