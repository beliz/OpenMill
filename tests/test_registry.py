from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from openmill.core.models import OperationRecord, Stock, Tool, Toolpath
from openmill.core.registry import OperationPlugin, OperationRegistry


class ExternalOperation(OperationPlugin):
    id = "external_operation_test"
    label = "Extension de test"
    category = "Extensions"
    description = "Opération fournie par un autre paquet."

    @classmethod
    def generate(cls, operation: OperationRecord, stock: Stock, tool: Tool) -> Toolpath:
        return cls.builder(operation, tool).result


class RegistryTests(unittest.TestCase):
    def test_external_entry_point_is_discovered(self) -> None:
        local_registry = OperationRegistry()
        entry_point = SimpleNamespace(name="test", load=lambda: ExternalOperation)
        with patch("openmill.core.registry.entry_points", return_value=(entry_point,)):
            local_registry.discover_entry_points()
        self.assertIs(local_registry.get(ExternalOperation.id), ExternalOperation)

    def test_entry_point_discovery_runs_only_once(self) -> None:
        local_registry = OperationRegistry()
        with patch("openmill.core.registry.entry_points", return_value=()) as discovery:
            local_registry.discover_entry_points()
            local_registry.discover_entry_points()
        discovery.assert_called_once_with(group="openmill.operations")

    def test_invalid_external_plugin_is_rejected(self) -> None:
        local_registry = OperationRegistry()
        entry_point = SimpleNamespace(name="invalid", load=lambda: object)
        with patch("openmill.core.registry.entry_points", return_value=(entry_point,)):
            with self.assertRaisesRegex(TypeError, "OperationPlugin"):
                local_registry.discover_entry_points()

    def test_duplicate_operation_id_is_rejected(self) -> None:
        local_registry = OperationRegistry()
        local_registry.register(ExternalOperation)
        with self.assertRaises(ValueError):
            local_registry.register(ExternalOperation)


if __name__ == "__main__":
    unittest.main()
