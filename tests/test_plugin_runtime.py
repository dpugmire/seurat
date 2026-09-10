import os
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    __import__("adios2")
except ModuleNotFoundError:
    adios2 = types.ModuleType("adios2")
    adios2.FileReader = object
    sys.modules["adios2"] = adios2


import plugin_runtime


class PersonalPluginDiscoveryTests(unittest.TestCase):
    def test_external_plugin_can_use_relative_helper_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp)
            (plugin_dir / "_helper.py").write_text(
                textwrap.dedent(
                    """
                    CHOICES = ['from-helper']

                    def supports_scalar(meta):
                        return meta.get('ndims') == 0
                    """
                ),
                encoding="utf-8",
            )
            (plugin_dir / "relative_plugin.py").write_text(
                textwrap.dedent(
                    """
                    from ._helper import CHOICES, supports_scalar

                    PLUGIN_ID = 'external_relative_import_test'
                    LABEL = 'External relative import test'

                    def supports(meta):
                        return supports_scalar(meta)

                    def options_schema(meta):
                        return [
                            {
                                'key': 'mode',
                                'type': 'select',
                                'label': 'Mode',
                                'choices': CHOICES,
                                'default': CHOICES[0],
                            }
                        ]
                    """
                ),
                encoding="utf-8",
            )

            missing_default_dir = plugin_dir / "missing-default"
            with patch.object(
                plugin_runtime,
                "DEFAULT_PERSONAL_PLUGIN_DIR",
                missing_default_dir,
            ), patch.dict(os.environ, {"SEURAT_PLUGIN_PATH": str(plugin_dir)}):
                discovered = {
                    info.plugin_id: info
                    for info in plugin_runtime.discover_plugins()
                }
                self.assertIn("external_relative_import_test", discovered)

                names = plugin_runtime.supported_plugin_visualizations({"ndims": 0})
                self.assertIn("plugin:external_relative_import_test", names)

                schema = plugin_runtime.plugin_options_schema(
                    "external_relative_import_test",
                    {"ndims": 0},
                )
                self.assertEqual(schema[0]["choices"], ["from-helper"])


if __name__ == "__main__":
    unittest.main()
