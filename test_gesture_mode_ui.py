from pathlib import Path
import unittest


class GestureModeUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")

    def test_all_four_gesture_axes_are_editable(self):
        for key in (
            "CONFIG_INPUT_IQS9151_2F_HORIZONTAL_MODE",
            "CONFIG_INPUT_IQS9151_2F_VERTICAL_MODE",
            "CONFIG_INPUT_IQS9151_3F_HORIZONTAL_MODE",
            "CONFIG_INPUT_IQS9151_3F_VERTICAL_MODE",
        ):
            self.assertIn(key, self.html)

    def test_mode_selector_offers_scroll_action_and_disabled(self):
        self.assertIn("label:'Key bindings'", self.html)
        self.assertIn("label:'Disabled'", self.html)
        self.assertIn("Horizontal Scroll", self.html)
        self.assertIn("Vertical Scroll", self.html)

    def test_left_and_right_configs_remain_independent(self):
        self.assertIn("state.tpConfigs[state.tpSide]", self.html)
        self.assertIn("const other=state.tpSide==='left'?'right':'left'", self.html)


if __name__ == "__main__":
    unittest.main()
