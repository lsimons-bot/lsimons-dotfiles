"""Focused tests for repository and machine validation."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "script"))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = load_module("dotfiles_check_validation", REPO_ROOT / "script" / "check.py")
helpers = load_module("dotfiles_helpers_validation", REPO_ROOT / "script" / "helpers.py")


class MachineValidationTests(unittest.TestCase):
    def test_validation_repository_machine_files_are_valid(self):
        self.assertEqual(check.check_machine_configs(), [])

    def test_validation_rejects_unknown_nested_key(self):
        errors = check.validate_machine_data(
            {"ssh": {"keys": [{"name": "key", "fingerpint": "bad"}]}},
            "machine.json",
        )
        self.assertTrue(any("fingerpint: unknown key" in error for error in errors))

    def test_validation_rejects_wrong_scalar_type(self):
        errors = check.validate_machine_data(
            {"claude": {"removeDenyRules": "yes"}}, "machine.json"
        )
        self.assertIn(
            "machine.json:$.claude.removeDenyRules: must be a boolean", errors
        )

    def test_validation_accepts_valid_providers_entry(self):
        errors = check.validate_machine_data(
            {
                "providers": {
                    "litellm": {
                        "op_account": "schubergphilis",
                        "op_ref": "op://Employee/litellm-pat/token",
                    }
                }
            },
            "machine.json",
        )
        self.assertEqual(errors, [])

    def test_validation_rejects_providers_missing_op_ref(self):
        errors = check.validate_machine_data(
            {"providers": {"litellm": {"op_account": "schubergphilis"}}},
            "machine.json",
        )
        self.assertIn(
            "machine.json:$.providers.litellm.op_ref: required key missing", errors
        )

    def test_validation_rejects_unknown_providers_field(self):
        errors = check.validate_machine_data(
            {
                "providers": {
                    "litellm": {
                        "op_account": "schubergphilis",
                        "op_ref": "op://Employee/litellm-pat/token",
                        "literal_secret": "nope",
                    }
                }
            },
            "machine.json",
        )
        self.assertTrue(any("literal_secret: unknown key" in error for error in errors))

    def test_validation_rejects_duplicate_and_non_signing_key_references(self):
        default = {
            "git": {
                "user": {
                    "name": "Test",
                    "email": "test@example.com",
                    "signingkey": "duplicate",
                }
            },
            "ssh": {
                "aiKey": "duplicate",
                "keys": [
                    {
                        "name": "duplicate",
                        "fingerprint": "SHA256:first",
                        "public_key": "ssh-ed25519 first",
                        "op_vault": "Test",
                        "op_account": "test",
                        "auth": False,
                        "sign": False,
                    },
                    {
                        "name": "duplicate",
                        "fingerprint": "SHA256:second",
                        "public_key": "ssh-ed25519 second",
                        "op_vault": "Test",
                        "op_account": "test",
                        "auth": False,
                        "sign": True,
                    },
                ],
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            machines_dir = repo_root / "machines"
            machines_dir.mkdir()
            (machines_dir / "default.json").write_text(json.dumps(default))
            with mock.patch.object(check, "REPO_ROOT", repo_root):
                errors = check.check_machine_configs()

        self.assertTrue(any("duplicate SSH key name" in error for error in errors))
        self.assertTrue(any("not enabled for signing" in error for error in errors))


class DryRunProbeTests(unittest.TestCase):
    def tearDown(self):
        helpers.set_dry_run(False)

    def test_validation_dry_run_probes_resources_as_absent(self):
        helpers.set_dry_run(True)
        self.assertFalse(helpers.command_exists("definitely-present-or-not"))
        self.assertFalse(helpers.app_exists("Example"))
        self.assertFalse(helpers.brew_is_installed("example"))


if __name__ == "__main__":
    unittest.main()
