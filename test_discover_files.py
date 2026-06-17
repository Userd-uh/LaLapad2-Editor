import os
import tempfile
import unittest

import app


class DiscoverFilesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        self.config_dir = os.path.join(self.root, 'config')
        os.makedirs(self.config_dir)
        open(os.path.join(self.config_dir, 'keyboard.keymap'), 'w').close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_accepts_firmware_root(self):
        found = app.discover_files(self.root)

        self.assertEqual(found['firmware_folder'], self.root)
        self.assertEqual(
            found['keymap_path'],
            os.path.join(self.config_dir, 'keyboard.keymap'),
        )

    def test_accepts_config_directory(self):
        found = app.discover_files(self.config_dir)

        self.assertEqual(found['firmware_folder'], self.root)
        self.assertEqual(
            found['keymap_path'],
            os.path.join(self.config_dir, 'keyboard.keymap'),
        )


if __name__ == '__main__':
    unittest.main()
