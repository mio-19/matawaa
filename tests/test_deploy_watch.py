"""Checks for the deployment actions that can change a watch's boot state."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "deployWatch.py"
spec = importlib.util.spec_from_file_location("deploy_watch", SCRIPT)
deploy_watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy_watch)


class DeployCopyTests(unittest.TestCase):
    def deploy(self, action):
        with (
            patch.object(deploy_watch, "build_asteroid_toplevel", return_value="/nix/store/system"),
            patch.object(deploy_watch, "check_ssh_connectivity"),
            patch.object(deploy_watch, "run_cmd") as run,
            patch.object(deploy_watch, "ssh_exec") as ssh,
        ):
            deploy_watch.deploy_copy(
                Path("/repo"), "fossil-hoki", "watch", 2222, "root",
                action, False, False,
            )
            return run.call_args, ssh.call_args

    def test_boot_stages_profile_and_uses_requested_ssh_port(self):
        copy, ssh = self.deploy("boot")
        self.assertIn("-p 2222", copy.kwargs["env"]["NIX_SSHOPTS"])
        self.assertIn("nix-env -p /nix/var/nix/profiles/system --set", ssh.args[3])
        self.assertIn("/bin/switch-to-configuration boot", ssh.args[3])

    def test_test_action_neither_flashes_nor_changes_default_profile(self):
        _, ssh = self.deploy("test")
        self.assertIn("switch-to-configuration test", ssh.args[3])
        self.assertNotIn("nix-env", ssh.args[3])

    def test_dry_run_never_connects_or_activates(self):
        with (
            patch.object(deploy_watch, "build_asteroid_toplevel", return_value="/nix/store/system"),
            patch.object(deploy_watch, "check_ssh_connectivity") as connect,
            patch.object(deploy_watch, "run_cmd") as run,
            patch.object(deploy_watch, "ssh_exec") as ssh,
        ):
            deploy_watch.deploy_copy(
                Path("/repo"), "fossil-hoki", "watch", 2222, "root",
                "boot", True, True,
            )
            connect.assert_not_called()
            run.assert_not_called()
            ssh.assert_not_called()

    def test_sudo_wraps_the_entire_remote_command(self):
        with patch.object(deploy_watch, "run_cmd") as run:
            deploy_watch.ssh_exec(
                "watch", 2222, "ceres", "first && second", sudo=True
            )
            command = run.call_args.args[0]
            self.assertIn("-tt", command)
            self.assertEqual(command[-1], "sudo -- sh -c 'first && second'")


if __name__ == "__main__":
    unittest.main()
