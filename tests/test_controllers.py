import unittest

import controllers as compatibility_controllers
from seurat.controllers import ControllerContext, SeuratController, attach_controllers
from seurat.controllers.composer import CONTROLLER_TYPES


class ControllerOwnershipTests(unittest.TestCase):
    def test_domain_bindings_are_unique_and_owned_by_the_declaring_controller(self):
        expected_counts = {
            "ACTION_BINDINGS": 85,
            "TRIGGER_BINDINGS": 7,
            "STATE_CHANGE_BINDINGS": 3,
        }

        for attribute, expected_count in expected_counts.items():
            names = []
            for controller_type in CONTROLLER_TYPES:
                for binding_name, method_name in getattr(controller_type, attribute):
                    names.append(binding_name)
                    self.assertIn(method_name, controller_type.__dict__)
                    self.assertTrue(callable(getattr(SeuratController, method_name)))

            self.assertEqual(len(names), expected_count)
            self.assertEqual(len(names), len(set(names)))

    def test_top_level_controller_module_is_a_compatibility_facade(self):
        self.assertIs(compatibility_controllers.ControllerContext, ControllerContext)
        self.assertIs(compatibility_controllers.SeuratController, SeuratController)
        self.assertIs(compatibility_controllers.attach_controllers, attach_controllers)


if __name__ == "__main__":
    unittest.main()
