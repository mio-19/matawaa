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
            patch.object(deploy_watch, "build_stage1_bootimg", return_value="/nix/store/boot.img") as build_boot,
            patch.object(deploy_watch, "flash_stage1_bootimg_remote") as flash_boot,
            patch.object(deploy_watch, "check_ssh_connectivity"),
            patch.object(deploy_watch, "run_cmd") as run,
            patch.object(deploy_watch, "ssh_exec") as ssh,
        ):
            deploy_watch.deploy_copy(
                Path("/repo"), "fossil-hoki", "watch", 2222, "root",
                action, False, True, False,
            )
            return build_boot.call_count, flash_boot.call_count, run.call_args, ssh.call_args

    def test_boot_stages_profile_and_uses_requested_ssh_port(self):
        build_count, flash_count, copy, ssh = self.deploy("boot")
        self.assertEqual((build_count, flash_count), (1, 1))
        self.assertIn("-p 2222", copy.kwargs["env"]["NIX_SSHOPTS"])
        self.assertIn("nix-env -p /nix/var/nix/profiles/system --set", ssh.args[3])
        self.assertNotIn("switch-to-configuration", ssh.args[3])

    def test_test_action_neither_flashes_nor_changes_default_profile(self):
        build_count, flash_count, _, ssh = self.deploy("test")
        self.assertEqual((build_count, flash_count), (0, 0))
        self.assertIn("switch-to-configuration test", ssh.args[3])
        self.assertNotIn("nix-env", ssh.args[3])

    def test_missing_boot_image_fails_before_transfer(self):
        with patch.object(deploy_watch, "run_cmd") as run:
            with self.assertRaises(FileNotFoundError):
                deploy_watch.flash_stage1_bootimg_remote(
                    "watch", 22, "root", "/nonexistent/boot.img"
                )
            run.assert_not_called()

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
