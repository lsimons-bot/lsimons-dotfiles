"""Tests for machine-aware provider credential resolution (issue #13).

Covers script/helpers.py::get_provider_credential and the
script/provider_credential.py CLI that codex.sh/opencode.sh call at
runtime to resolve the LiteLLM 1Password account/reference from the
CURRENT machine's config, with fail-closed behaviour and no fallback
to another machine's credential.
"""

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "script"))

import helpers

CONFIGURED_MACHINE = {
    "providers": {
        "litellm": {
            "op_account": "schubergphilis",
            "op_ref": "op://Employee/litellm-pat/token",
        }
    }
}

OTHER_MACHINE = {
    "providers": {
        "litellm": {
            "op_account": "some-other-account",
            "op_ref": "op://Vault/other-item/token",
        }
    }
}

UNCONFIGURED_MACHINE = {"git": {"user": {"name": "Test", "email": "t@example.com"}}}


class GetProviderCredentialTests(unittest.TestCase):
    def test_configured_machine_resolves_its_own_credential(self):
        with mock.patch.object(
            helpers, "get_machine_config", return_value=(CONFIGURED_MACHINE, "work")
        ):
            op_account, op_ref = helpers.get_provider_credential("litellm")

        self.assertEqual(op_account, "schubergphilis")
        self.assertEqual(op_ref, "op://Employee/litellm-pat/token")

    def test_unconfigured_machine_fails_closed(self):
        with (
            mock.patch.object(
                helpers, "get_machine_config", return_value=(UNCONFIGURED_MACHINE, "personal")
            ),
            self.assertRaises(ValueError) as ctx,
        ):
            helpers.get_provider_credential("litellm")

        self.assertIn("personal", str(ctx.exception))
        self.assertIn("litellm", str(ctx.exception))

    def test_no_fallback_to_another_machines_credential(self):
        # A machine with no providers.litellm entry must never resolve to
        # values configured for some other machine, even though another
        # machine (e.g. the work laptop) has a valid entry.
        with (
            mock.patch.object(
                helpers, "get_machine_config", return_value=(UNCONFIGURED_MACHINE, "personal")
            ),
            self.assertRaises(ValueError),
        ):
            helpers.get_provider_credential("litellm")

        with mock.patch.object(
            helpers, "get_machine_config", return_value=(OTHER_MACHINE, "other")
        ):
            op_account, op_ref = helpers.get_provider_credential("litellm")

        self.assertNotEqual(op_account, "schubergphilis")
        self.assertNotEqual(op_ref, "op://Employee/litellm-pat/token")

    def test_incomplete_entry_fails_closed(self):
        machine = {"providers": {"litellm": {"op_account": "schubergphilis"}}}
        with (
            mock.patch.object(helpers, "get_machine_config", return_value=(machine, "work")),
            self.assertRaises(ValueError),
        ):
            helpers.get_provider_credential("litellm")

    def test_unknown_provider_fails_closed(self):
        with (
            mock.patch.object(
                helpers, "get_machine_config", return_value=(CONFIGURED_MACHINE, "work")
            ),
            self.assertRaises(ValueError),
        ):
            helpers.get_provider_credential("some-other-provider")


class ProviderCredentialCliTests(unittest.TestCase):
    """Exercise the CLI shell wrappers actually invoke, end-to-end.

    These run against whatever machine config is active in this repo
    checkout (i.e. no per-machine match, since CI hostnames won't match
    anything in machines/*.json), so they only assert the argument
    handling and fail-closed contract that codex.sh/opencode.sh depend
    on: no stdout and a non-zero exit code on failure.
    """

    def test_missing_argument_exits_nonzero(self):
        script = REPO_ROOT / "script" / "provider_credential.py"
        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, check=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage", result.stderr)

    def test_unknown_provider_exits_nonzero_with_no_stdout(self):
        script = REPO_ROOT / "script" / "provider_credential.py"
        result = subprocess.run(
            [sys.executable, str(script), "totally-unsupported-provider"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("totally-unsupported-provider", result.stderr)


if __name__ == "__main__":
    unittest.main()
