"""Tests for the macOS/Linux platform abstraction.

These cover the pieces that decide *what* runs where — package-manager
dispatch, per-topic platform gating, and per-platform symlink
destinations — rather than any one topic's installer.
"""

import contextlib
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "script"))

import helpers


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load_module("dotfiles_platform_installer", REPO_ROOT / "script" / "install.py")


def _on(macos=False, arch=False, debian=False):
    """Force the platform flags helpers.ensure_package dispatches on."""
    stack = contextlib.ExitStack()
    stack.enter_context(mock.patch.object(helpers, "IS_MACOS", macos))
    stack.enter_context(mock.patch.object(helpers, "IS_LINUX", arch or debian))
    stack.enter_context(mock.patch.object(helpers, "IS_ARCH", arch))
    stack.enter_context(mock.patch.object(helpers, "IS_DEBIAN", debian))
    return stack


def _on_arch():
    return _on(arch=True)


def _on_debian():
    return _on(debian=True)


class DistroDetectionTests(unittest.TestCase):
    def _ids(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "os-release"
            path.write_text(text)
            return helpers._linux_distro_ids(path)

    def test_id_like_marks_arch_derivatives_as_arch(self):
        """Omarchy runs Arch Linux ARM, whose ID is archarm, not arch."""
        ids = self._ids('NAME="Arch Linux ARM"\nID=archarm\nID_LIKE=arch\n')
        self.assertIn("arch", ids)
        self.assertIn("archarm", ids)

    def test_quoted_and_multi_valued_id_like_is_split(self):
        ids = self._ids('ID=omarchy\nID_LIKE="arch archarm"\n')
        self.assertEqual(ids, {"omarchy", "arch", "archarm"})

    def test_missing_os_release_is_not_an_error(self):
        self.assertEqual(
            helpers._linux_distro_ids(Path("/nonexistent/os-release")), set()
        )

    def test_ubuntu_is_a_debian_derivative(self):
        ids = self._ids('ID=ubuntu\nID_LIKE=debian\nVERSION_CODENAME=noble\n')
        self.assertTrue({"debian", "ubuntu"} & ids)
        self.assertNotIn("arch", ids)


class WslDetectionTests(unittest.TestCase):
    def _proc_version(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "version"
        path.write_text(text)
        return path

    def test_wsl_session_variable_is_enough(self):
        with mock.patch.dict(helpers.os.environ, {"WSL_DISTRO_NAME": "Ubuntu-24.04"}):
            self.assertTrue(helpers._running_in_wsl(Path("/nonexistent")))

    def test_microsoft_kernel_is_detected_without_the_variable(self):
        proc = self._proc_version(
            "Linux version 6.6.87.2-microsoft-standard-WSL2 (root@...) #1 SMP\n"
        )
        with mock.patch.dict(helpers.os.environ, {}, clear=True):
            self.assertTrue(helpers._running_in_wsl(proc))

    def test_plain_linux_is_not_wsl(self):
        proc = self._proc_version("Linux version 6.12.1-arch1-1 (linux@archlinux)\n")
        with mock.patch.dict(helpers.os.environ, {}, clear=True):
            self.assertFalse(helpers._running_in_wsl(proc))


class EnsurePackageTests(unittest.TestCase):
    def setUp(self):
        helpers.set_dry_run(False)

    def test_command_probe_short_circuits_before_any_package_manager(self):
        with mock.patch.object(
            helpers, "command_exists", return_value=True
        ), mock.patch.object(helpers, "brew_install") as brew, mock.patch.object(
            helpers, "pacman_install"
        ) as pacman:
            self.assertTrue(helpers.ensure_package("jq", brew="jq", pacman="jq", command="jq"))
        brew.assert_not_called()
        pacman.assert_not_called()

    def test_macos_uses_brew_and_linux_uses_pacman(self):
        for is_macos, installed_with in ((True, "brew"), (False, "pacman")):
            with self.subTest(macos=is_macos), mock.patch.object(
                helpers, "IS_MACOS", is_macos
            ), mock.patch.object(helpers, "IS_LINUX", not is_macos), mock.patch.object(
                helpers, "IS_ARCH", not is_macos
            ), mock.patch.object(helpers, "IS_DEBIAN", False), mock.patch.object(
                helpers, "brew_is_installed", return_value=False
            ), mock.patch.object(
                helpers, "pacman_is_installed", return_value=False
            ), mock.patch.object(
                helpers, "pacman_repo_of", return_value="extra"
            ), mock.patch.object(
                helpers, "brew_install", return_value=True
            ) as brew, mock.patch.object(
                helpers, "pacman_install", return_value=True
            ) as pacman:
                self.assertTrue(
                    helpers.ensure_package("gh", brew="gh", pacman="github-cli")
                )
                if installed_with == "brew":
                    brew.assert_called_once_with("gh", cask=False)
                    pacman.assert_not_called()
                else:
                    pacman.assert_called_once_with("extra/github-cli")
                    brew.assert_not_called()

    def test_aur_fallback_when_the_package_is_in_no_repo(self):
        with mock.patch.object(helpers, "IS_MACOS", False), _on_arch(), mock.patch.object(
            helpers, "pacman_is_installed", return_value=False
        ), mock.patch.object(
            helpers, "pacman_repo_of", return_value=None
        ), mock.patch.object(
            helpers, "pacman_install"
        ) as pacman, mock.patch.object(
            helpers, "aur_install", return_value=True
        ) as aur:
            self.assertTrue(helpers.ensure_package("topgrade", aur="topgrade"))
        pacman.assert_not_called()
        aur.assert_called_once_with("topgrade")

    def test_missing_package_name_for_this_platform_fails_loudly(self):
        """A topic with no Arch package must not quietly report success."""
        with mock.patch.object(helpers, "IS_MACOS", False), _on_arch(), mock.patch.object(helpers, "command_exists", return_value=False):
            self.assertFalse(helpers.ensure_package("dockutil", brew="dockutil"))

    def test_optional_downgrades_a_missing_package_to_a_warning(self):
        with mock.patch.object(helpers, "IS_MACOS", False), _on_arch(), mock.patch.object(helpers, "command_exists", return_value=False):
            self.assertTrue(
                helpers.ensure_package("dockutil", brew="dockutil", optional=True)
            )

    def test_optional_also_absorbs_an_install_failure(self):
        with mock.patch.object(helpers, "IS_MACOS", False), _on_arch(), mock.patch.object(
            helpers, "command_exists", return_value=False
        ), mock.patch.object(
            helpers, "pacman_is_installed", return_value=False
        ), mock.patch.object(
            helpers, "pacman_repo_of", return_value=None
        ), mock.patch.object(helpers, "aur_install", return_value=False):
            self.assertTrue(
                helpers.ensure_package("ghostty", pacman="ghostty", optional=True)
            )

    def test_debian_uses_apt(self):
        with _on_debian(), mock.patch.object(
            helpers, "command_exists", return_value=False
        ), mock.patch.object(
            helpers, "apt_is_installed", return_value=False
        ), mock.patch.object(
            helpers, "apt_install", return_value=True
        ) as apt, mock.patch.object(
            helpers, "pacman_install"
        ) as pacman, mock.patch.object(helpers, "mise_use") as mise:
            self.assertTrue(
                helpers.ensure_package(
                    "GitHub CLI", brew="gh", pacman="github-cli", apt="gh", mise="gh"
                )
            )
        apt.assert_called_once_with("gh")
        pacman.assert_not_called()
        mise.assert_not_called()

    def test_mise_is_the_fallback_where_no_native_package_is_named(self):
        with _on_debian(), mock.patch.object(
            helpers, "command_exists", return_value=True
        ), mock.patch.object(
            helpers, "apt_install"
        ) as apt, mock.patch.object(helpers, "mise_use", return_value=True) as mise:
            # command_exists is True for the "mise" prerequisite probe, so
            # skip the tool's own probe by not passing command=.
            self.assertTrue(
                helpers.ensure_package("herdr", brew="herdr", pacman="herdr", mise="herdr")
            )
        mise.assert_called_once_with("herdr")
        apt.assert_not_called()

    def test_a_native_package_beats_the_mise_fallback(self):
        with _on_arch(), mock.patch.object(
            helpers, "command_exists", return_value=False
        ), mock.patch.object(
            helpers, "pacman_is_installed", return_value=False
        ), mock.patch.object(
            helpers, "pacman_repo_of", return_value="extra"
        ), mock.patch.object(
            helpers, "pacman_install", return_value=True
        ) as pacman, mock.patch.object(helpers, "mise_use") as mise:
            self.assertTrue(helpers.ensure_package("uv", pacman="uv", mise="uv"))
        pacman.assert_called_once_with("extra/uv")
        mise.assert_not_called()

    def test_mise_fallback_needs_mise_installed(self):
        with _on_debian(), mock.patch.object(
            helpers, "command_exists", return_value=False
        ), mock.patch.object(helpers, "mise_use") as mise:
            self.assertFalse(helpers.ensure_package("herdr", mise="herdr"))
        mise.assert_not_called()

    def test_apt_probe_reads_dpkg_status(self):
        installed = subprocess.CompletedProcess([], 0, stdout="install ok installed", stderr="")
        removed = subprocess.CompletedProcess([], 0, stdout="deinstall ok config-files", stderr="")
        with mock.patch.object(helpers.subprocess, "run", return_value=installed):
            self.assertTrue(helpers.apt_is_installed("jq"))
        with mock.patch.object(helpers.subprocess, "run", return_value=removed):
            self.assertFalse(helpers.apt_is_installed("jq"))

    def test_dry_run_installs_nothing_and_reports_success(self):
        helpers.set_dry_run(True)
        self.addCleanup(helpers.set_dry_run, False)
        with _on_arch(), mock.patch.object(helpers.subprocess, "run") as run:
            self.assertTrue(
                helpers.ensure_package("jq", brew="jq", pacman="jq", command="jq")
            )
        run.assert_not_called()


class PacmanTargetQualificationTests(unittest.TestCase):
    """Repo targets must be installed as ``<repo>/<package>``.

    A repository can set `Usage` in pacman.conf to exclude `Install`, and
    Omarchy's own repo does (`Usage = Sync`). Under that setting
    `pacman -Si 1password` describes the package but `pacman -S
    1password` fails with "target not found" — only
    `pacman -S omarchy/1password` works. Installing by bare name made
    every Omarchy-repo package look absent and fall through to an AUR
    source build, or fail outright.
    """

    def setUp(self):
        helpers.set_dry_run(False)

    def _completed(self, returncode, stdout=""):
        return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")

    def test_repo_is_read_from_pacman_si_output(self):
        output = (
            "Repository      : omarchy\n"
            "Name            : 1password\n"
            "Version         : 8.12.34-35\n"
        )
        with mock.patch.object(
            helpers.subprocess, "run", return_value=self._completed(0, output)
        ):
            self.assertEqual(helpers.pacman_repo_of("1password"), "omarchy")

    def test_unknown_package_has_no_repo(self):
        with mock.patch.object(
            helpers.subprocess, "run", return_value=self._completed(1)
        ):
            self.assertIsNone(helpers.pacman_repo_of("nope"))

    def test_install_target_carries_the_repo_prefix(self):
        with mock.patch.object(helpers, "IS_MACOS", False), _on_arch(), mock.patch.object(
            helpers, "command_exists", return_value=False
        ), mock.patch.object(
            helpers, "pacman_is_installed", return_value=False
        ), mock.patch.object(
            helpers, "pacman_repo_of", return_value="omarchy"
        ), mock.patch.object(
            helpers, "pacman_install", return_value=True
        ) as pacman, mock.patch.object(helpers, "aur_install") as aur:
            self.assertTrue(
                helpers.ensure_package("1Password app", pacman="1password")
            )
        pacman.assert_called_once_with("omarchy/1password")
        aur.assert_not_called()

    def test_an_aur_name_carried_by_a_repo_skips_the_source_build(self):
        """Omarchy prebuilds plenty of AUR packages; prefer those."""
        with mock.patch.object(helpers, "IS_MACOS", False), _on_arch(), mock.patch.object(
            helpers, "command_exists", return_value=False
        ), mock.patch.object(
            helpers, "pacman_is_installed", return_value=False
        ), mock.patch.object(
            helpers,
            "pacman_repo_of",
            side_effect=lambda name: "omarchy" if name == "mise-bin" else None,
        ), mock.patch.object(
            helpers, "pacman_install", return_value=True
        ) as pacman, mock.patch.object(helpers, "aur_install") as aur:
            self.assertTrue(
                helpers.ensure_package("mise", pacman="mise", aur="mise-bin")
            )
        pacman.assert_called_once_with("omarchy/mise-bin")
        aur.assert_not_called()


class AptRepositoryBootstrapTests(unittest.TestCase):
    """The Debian bootstrap adds vendor apt repositories exactly once."""

    def _repo(self, root):
        return {
            'name': 'mise',
            'key_url': 'https://example.invalid/key.pub',
            'keyring': root / 'keyrings' / 'mise.gpg',
            'source': 'deb [arch={arch} signed-by={keyring}] https://example.invalid/deb stable main',
            'list': root / 'sources.list.d' / 'mise.list',
        }

    def _write(self, path, data, mode='0644'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def test_first_run_writes_key_and_source_and_second_run_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            installer, "fetch_url", return_value=b"binary-key"
        ) as fetch, mock.patch.object(installer, "sudo_write", side_effect=self._write):
            repo = self._repo(Path(tmp))
            self.assertTrue(installer.ensure_apt_repo(repo, "amd64"))
            self.assertEqual(repo['keyring'].read_bytes(), b"binary-key")
            self.assertEqual(
                repo['list'].read_text(),
                f"deb [arch=amd64 signed-by={repo['keyring']}] "
                "https://example.invalid/deb stable main\n",
            )
            fetch.assert_called_once()
            self.assertFalse(installer.ensure_apt_repo(repo, "amd64"))
            fetch.assert_called_once()

    def test_a_changed_source_line_is_rewritten_without_refetching_the_key(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            installer, "fetch_url"
        ) as fetch, mock.patch.object(installer, "sudo_write", side_effect=self._write):
            repo = self._repo(Path(tmp))
            self._write(repo['keyring'], b"binary-key")
            self._write(repo['list'], b"deb https://example.invalid/old stable main\n")
            self.assertTrue(installer.ensure_apt_repo(repo, "arm64"))
            self.assertIn("arch=arm64", repo['list'].read_text())
            fetch.assert_not_called()

    def test_a_repo_already_managed_by_extrepo_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            installer, "fetch_url"
        ) as fetch, mock.patch.object(installer, "sudo_write") as write:
            repo = self._repo(Path(tmp))
            managed = Path(tmp) / "sources.list.d" / "extrepo_mise.sources"
            self._write(managed, b"Types: deb\n")
            repo['managed_by'] = [managed]
            self.assertFalse(installer.ensure_apt_repo(repo, "amd64"))
        fetch.assert_not_called()
        write.assert_not_called()

    def test_downloads_identify_themselves(self):
        """mise.jdx.dev returns 403 to Python's default user agent."""
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"key"
        with mock.patch.object(installer.urllib.request, "urlopen", return_value=response) as urlopen:
            self.assertEqual(installer.fetch_url("https://example.invalid/key"), b"key")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.invalid/key")
        self.assertNotIn("urllib", request.get_header("User-agent", ""))
        self.assertIn("lsimons-dotfiles", request.get_header("User-agent", ""))

    def test_armored_keys_are_dearmored_and_binary_keys_pass_through(self):
        self.assertEqual(installer.dearmor(b"\x99\x02binary"), b"\x99\x02binary")
        done = subprocess.CompletedProcess([], 0, stdout=b"dearmored", stderr=b"")
        with mock.patch.object(installer.subprocess, "run", return_value=done) as run:
            self.assertEqual(
                installer.dearmor(b"-----BEGIN PGP PUBLIC KEY BLOCK-----\n..."), b"dearmored"
            )
        self.assertEqual(run.call_args.args[0], ['gpg', '--dearmor'])


class BrewWithoutHomebrewTests(unittest.TestCase):
    """The brew_* helpers are called on Linux by legacy-migration paths."""

    def setUp(self):
        helpers.set_dry_run(False)

    def test_probes_answer_no_rather_than_raising(self):
        with mock.patch.object(helpers.shutil, "which", return_value=None):
            self.assertFalse(helpers.brew_is_installed("gemini-cli"))
            # "Nothing to uninstall" is success, not failure.
            self.assertTrue(helpers.brew_uninstall("gemini-cli"))
            self.assertFalse(helpers.brew_install("gemini-cli"))


class NpmGlobalInstalledTests(unittest.TestCase):
    """npm_global_installed asks npm, not PATH, whether a package is present."""

    def setUp(self):
        helpers.set_dry_run(False)

    def test_asks_npm_about_the_active_node(self):
        done = subprocess.CompletedProcess([], 0, stdout=b"", stderr=b"")
        with mock.patch.object(helpers.shutil, "which", return_value="/usr/bin/npm"), \
                mock.patch.object(helpers.subprocess, "run", return_value=done) as run:
            self.assertTrue(helpers.npm_global_installed("ccusage"))
        self.assertEqual(run.call_args.args[0], ["npm", "ls", "--global", "--depth=0", "ccusage"])

    def test_stale_mise_shim_counts_as_absent(self):
        # The shim is on PATH, but the active node has no such package.
        missing = subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"")
        with mock.patch.object(helpers.shutil, "which", return_value="/shims/ccusage"), \
                mock.patch.object(helpers.subprocess, "run", return_value=missing):
            self.assertFalse(helpers.npm_global_installed("ccusage"))

    def test_without_npm_answers_no_rather_than_raising(self):
        with mock.patch.object(helpers.shutil, "which", return_value=None):
            self.assertFalse(helpers.npm_global_installed("ccusage"))


class TopicPlatformTests(unittest.TestCase):
    def test_topic_without_platforms_txt_runs_everywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(installer.get_topic_platforms(Path(tmp)))
            self.assertTrue(installer.topic_supported(Path(tmp)))

    def test_platforms_txt_gates_the_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            topic = Path(tmp)
            (topic / "platforms.txt").write_text("# only on a Mac\nmacos\n")
            self.assertEqual(installer.get_topic_platforms(topic), {"macos"})
            with mock.patch.object(installer, "HOST_PLATFORMS", {"macos"}):
                self.assertTrue(installer.topic_supported(topic))
            with mock.patch.object(installer, "HOST_PLATFORMS", {"linux", "linux-desktop"}):
                self.assertFalse(installer.topic_supported(topic))

    def test_linux_desktop_topics_are_skipped_under_wsl(self):
        with tempfile.TemporaryDirectory() as tmp:
            topic = Path(tmp)
            (topic / "platforms.txt").write_text("macos\nlinux-desktop\n")
            with mock.patch.object(installer, "HOST_PLATFORMS", {"linux", "linux-desktop"}):
                self.assertTrue(installer.topic_supported(topic))
            with mock.patch.object(installer, "HOST_PLATFORMS", {"linux"}):
                self.assertFalse(installer.topic_supported(topic))

    def test_repo_desktop_topics_are_declared(self):
        """The Windows host owns the editor, browser, fonts and desktop
        theming under WSL, so these must never run there."""
        for name in ("zed", "ghostty", "vivaldi", "fonts"):
            with self.subTest(topic=name):
                self.assertEqual(
                    installer.get_topic_platforms(REPO_ROOT / name),
                    {"macos", "linux-desktop"},
                )
        self.assertEqual(
            installer.get_topic_platforms(REPO_ROOT / "omarchy"), {"linux-desktop"}
        )

    def test_repo_macos_only_topics_are_declared(self):
        """These topics drive Dock/Terminal.app/swiftDialog or replace a
        tool Linux already has, so they must never run on Linux."""
        for name in ("dock", "terminal", "swiftdialog", "timeout"):
            with self.subTest(topic=name):
                self.assertEqual(
                    installer.get_topic_platforms(REPO_ROOT / name), {"macos"}
                )


class PlatformSymlinkMappingTests(unittest.TestCase):
    def test_platform_prefix_selects_one_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            topic = Path(tmp)
            (topic / "symlinks.txt").write_text(
                "# comment\n"
                "macos: config.symlink -> $HOME/Library/App/config\n"
                "linux: config.symlink -> $XDG_CONFIG_HOME/app/config\n"
                "theme.symlink -> $XDG_CONFIG_HOME/app/theme\n"
            )
            mac = helpers.load_symlink_mappings(topic, "macos")
            linux = helpers.load_symlink_mappings(topic, "linux")

        self.assertTrue(str(mac["config.symlink"]).endswith("/Library/App/config"))
        self.assertTrue(str(linux["config.symlink"]).endswith("/app/config"))
        # An unprefixed line applies on both.
        self.assertEqual(mac["theme.symlink"], linux["theme.symlink"])

    def test_ghostty_config_lands_in_the_native_location_on_each_platform(self):
        mac = helpers.load_symlink_mappings(REPO_ROOT / "ghostty", "macos")
        linux = helpers.load_symlink_mappings(REPO_ROOT / "ghostty", "linux")
        self.assertIn(
            "Library/Application Support/com.mitchellh.ghostty",
            str(mac["config.symlink"]),
        )
        self.assertNotIn("Library", str(linux["config.symlink"]))
        self.assertTrue(str(linux["config.symlink"]).endswith("/ghostty/config"))


class OnePasswordIntegrationPathTests(unittest.TestCase):
    """1Password installs its agent socket and signing shim elsewhere on Linux.

    Both are module-level constants derived from helpers.IS_MACOS, so the
    modules are re-imported with that flag forced either way.
    """

    def _load(self, name, relative_path, is_macos, is_wsl=False):
        with mock.patch.object(helpers, "IS_MACOS", is_macos), mock.patch.object(
            helpers, "IS_WSL", is_wsl
        ):
            return load_module(f"{name}_{is_macos}_{is_wsl}", REPO_ROOT / relative_path)

    def test_ssh_agent_socket_is_platform_native(self):
        mac = self._load("ssh_installer", "ssh/install.py", True)
        linux = self._load("ssh_installer", "ssh/install.py", False)
        self.assertIn(
            "Library/Group Containers/2BUA8C4S2C.com.1password",
            str(mac.OP_AGENT_SOCKET),
        )
        self.assertTrue(str(linux.OP_AGENT_SOCKET).endswith("/.1password/agent.sock"))

    def test_op_ssh_sign_is_platform_native(self):
        mac = self._load("git_installer", "git/install.py", True)
        linux = self._load("git_installer", "git/install.py", False)
        self.assertEqual(
            mac.GPG_SSH_PROGRAM_DEFAULT,
            "/Applications/1Password.app/Contents/MacOS/op-ssh-sign",
        )
        self.assertEqual(linux.GPG_SSH_PROGRAM_DEFAULT, "/opt/1Password/op-ssh-sign")

    def test_wsl_signs_through_the_bridged_agent(self):
        """No desktop app means no op-ssh-sign; the generated helper signs
        with ssh-keygen against the bridged agent, at the Linux socket path."""
        git = self._load("git_installer", "git/install.py", False, is_wsl=True)
        ssh = self._load("ssh_installer", "ssh/install.py", False, is_wsl=True)
        self.assertEqual(git.GPG_SSH_PROGRAM_DEFAULT, str(helpers.SSH_SIGN_BRIDGE_PATH))
        self.assertEqual(ssh.OP_AGENT_SOCKET, helpers.OP_LINUX_AGENT_SOCKET)


class GitEditorFallbackTests(unittest.TestCase):
    """core.editor must name an editor that is actually installed.

    Zed has no aarch64 Linux build, so hard-coding `zed --wait` there
    leaves git launching a binary that is not there.
    """

    def setUp(self):
        self.git_installer = load_module(
            "dotfiles_git_editor", REPO_ROOT / "git" / "install.py"
        )

    def test_prefers_zed_when_present(self):
        with mock.patch.object(
            self.git_installer, "command_exists", lambda cmd: cmd == "zed"
        ):
            self.assertEqual(self.git_installer.resolve_editor(), "zed --wait")

    def test_uses_the_linux_zed_binary_name(self):
        with mock.patch.object(
            self.git_installer, "command_exists", lambda cmd: cmd == "zeditor"
        ):
            self.assertEqual(self.git_installer.resolve_editor(), "zeditor --wait")

    def test_falls_back_to_a_terminal_editor(self):
        with mock.patch.object(
            self.git_installer, "command_exists", lambda cmd: cmd == "nvim"
        ):
            self.assertEqual(self.git_installer.resolve_editor(), "nvim")

    def test_falls_back_to_vim_when_nothing_is_installed(self):
        with mock.patch.object(
            self.git_installer, "command_exists", return_value=False
        ):
            self.assertEqual(self.git_installer.resolve_editor(), "vim")


class GitCredentialHelperTests(unittest.TestCase):
    """credential.helper must name a helper that can actually run.

    Git Credential Manager has no Debian/Ubuntu package (so none under
    WSL either), and the AUR build is optional. Where it is missing, gh
    stands in; otherwise a non-interactive `git push` dies with
    "'credential-manager' is not a git command".
    """

    def setUp(self):
        self.git_installer = load_module(
            "dotfiles_git_credential", REPO_ROOT / "git" / "install.py"
        )

    def test_prefers_git_credential_manager_when_present(self):
        with mock.patch.object(
            self.git_installer,
            "command_exists",
            lambda cmd: cmd == "git-credential-manager",
        ):
            self.assertEqual(self.git_installer.resolve_credential_helper(), "manager")

    def test_falls_back_to_gh_when_gcm_is_missing(self):
        with mock.patch.object(
            self.git_installer, "command_exists", return_value=False
        ):
            self.assertEqual(
                self.git_installer.resolve_credential_helper(),
                "!gh auth git-credential",
            )

    def test_template_renders_the_resolved_helper(self):
        template = (REPO_ROOT / "git" / "config.template").read_text()
        rendered = self.git_installer._render_config(
            template,
            allowed_signers_file="/tmp/signers",
            name="Test User",
            email="t@example.com",
            gpgsign="true",
            signingkey="",
            gpg_ssh_program="ssh-keygen",
            editor="vim",
            credential_helper="!gh auth git-credential",
            ssh_command_block="",
        )
        self.assertIn("\thelper =\n\thelper = !gh auth git-credential\n", rendered)
        self.assertNotIn("helper = manager", rendered)


if __name__ == "__main__":
    unittest.main()
