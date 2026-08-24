#!/usr/bin/python3
import importlib.machinery
import importlib.util
import os
import stat
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def load_homing():
    path = Path(__file__).resolve().parents[1] / "bin" / "homing"
    loader = importlib.machinery.SourceFileLoader("homing", str(path))
    spec = importlib.util.spec_from_loader("homing", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["homing"] = module
    loader.exec_module(module)
    return module


H = load_homing()


class RegexTests(unittest.TestCase):
    def test_escape_desktop_id(self):
        self.assertEqual(H.re2_escape("com.mitchellh.ghostty"), r"com\.mitchellh\.ghostty")

    def test_chromium_family_regex(self):
        regex = H.class_regex_for("chromium")
        self.assertEqual(regex, r"^([Cc]hromium(-browser)?)$")
        self.assertEqual(H.class_regex_for("Chromium-browser"), regex)

    def test_exact_class_regex(self):
        self.assertEqual(H.class_regex_for("slack"), r"^(slack)$")

    def test_pwa_class_is_exact(self):
        pwa = "chrome-cinhimbnkkaeohfgghhklpknlkffjgod-Default"
        self.assertIn(H.re2_escape(pwa), H.class_regex_for(pwa))
        self.assertIsNone(H.family_for_class(pwa))


class AssignmentTests(unittest.TestCase):
    def test_ids_and_tags(self):
        self.assertEqual(H.assignment_id("class", "slack"), "class:slack")
        self.assertEqual(H.assignment_id("class", "Chromium-browser"), "class:chromium")
        self.assertEqual(H.assignment_id("profile", "chromium", "Profile 1"), "profile:chromium:Profile 1")
        self.assertEqual(H.tag_for_profile("chromium", "Profile 1"), "homing-chromium-profile-1")
        self.assertEqual(H.tag_for_profile("chromium", "Default"), "homing-chromium-default")

    def test_upsert_replaces_same_id(self):
        store = H.empty_store()
        first = {"id": "class:slack", "kind": "class", "class": "slack", "workspace": "3"}
        second = {"id": "class:slack", "kind": "class", "class": "slack", "workspace": "5"}
        H.upsert_assignment(store, first)
        H.upsert_assignment(store, second)
        self.assertEqual(len(store["assignments"]), 1)
        self.assertEqual(store["assignments"][0]["workspace"], "5")

    def test_profile_does_not_replace_class(self):
        store = H.empty_store()
        H.upsert_assignment(store, {"id": "class:chromium", "kind": "class", "class": "chromium", "workspace": "1"})
        H.upsert_assignment(
            store,
            {
                "id": "profile:chromium:Default",
                "kind": "profile",
                "class": "chromium",
                "profile_directory": "Default",
                "workspace": "2",
            },
        )
        self.assertEqual(len(store["assignments"]), 2)


class LuaTests(unittest.TestCase):
    def test_empty_store(self):
        lua = H.generate_lua(H.empty_store())
        self.assertIn("No assignments yet", lua)
        self.assertIn("return true", lua)

    def test_class_rule(self):
        store = H.empty_store()
        H.upsert_assignment(
            store,
            {
                "id": "class:slack",
                "kind": "class",
                "class": "slack",
                "class_regex": "^(slack)$",
                "workspace": "3",
                "label": "slack",
            },
        )
        lua = H.generate_lua(store)
        self.assertIn('name = "homing-class-slack"', lua)
        self.assertIn('class = "^(slack)$"', lua)
        self.assertIn('workspace = "3"', lua)
        self.assertNotIn("window.open_early", lua)

    def test_profile_rule_includes_tagger(self):
        store = H.empty_store()
        H.upsert_assignment(
            store,
            {
                "id": "profile:chromium:Profile 1",
                "kind": "profile",
                "class": "chromium",
                "profile_directory": "Profile 1",
                "profile_name": "Private",
                "user_data_dir": "/home/reinier/.config/chromium",
                "tag": "homing-chromium-profile-1",
                "workspace": "5",
                "label": "Chromium (Private)",
            },
        )
        lua = H.generate_lua(store)
        self.assertIn("window.open_early", lua)
        self.assertIn("homing_detect_profile", lua)
        self.assertIn('directory = "Profile 1"', lua)
        self.assertIn('tag = "homing-chromium-profile-1"', lua)
        self.assertIn('match = { tag = "homing-chromium-profile-1" }', lua)
        self.assertIn('workspace = "5"', lua)
        self.assertIn("hl.dsp.window.move", lua)
        self.assertIn("/home/reinier/.config/chromium", lua)
        self.assertNotIn('*a', lua)
        self.assertIn("file:read(max_len)", lua)
        self.assertIn('homing_read("/proc/" .. tostring(pid) .. "/status", 65536)', lua)
        self.assertIn('homing_read("/proc/" .. tostring(current) .. "/cmdline", 65536)', lua)
        self.assertIn('homing_read("/proc/" .. tostring(current) .. "/maps", 2097152)', lua)

    def test_lua_string_escapes(self):
        self.assertEqual(H.lua_string('a"b\\c'), r'"a\"b\\c"')


class HookTests(unittest.TestCase):
    def test_inject_before_hyprmoncfg(self):
        original = (
            "require(\"hypr.autostart\")\n\n"
            "-- Added by hyprmoncfg: keep last.\n"
            "dofile(os.getenv(\"HOME\") .. \"/hyprmoncfg-monitors.lua\")\n"
        )
        updated = H.inject_hyprland_hook(original)
        self.assertIn('pcall(require, "hypr.homing")', updated)
        self.assertLess(updated.index("hypr.homing"), updated.index("hyprmoncfg"))
        self.assertEqual(H.inject_hyprland_hook(updated), updated)

    def test_inject_appends_without_marker(self):
        original = 'require("hypr.bindings")\n'
        updated = H.inject_hyprland_hook(original)
        self.assertTrue(updated.endswith('pcall(require, "hypr.homing")\n'))

    def test_remove_reverses_hyprmoncfg_inject(self):
        original = (
            "require(\"hypr.autostart\")\n\n"
            "-- Added by hyprmoncfg: keep last.\n"
            "dofile(os.getenv(\"HOME\") .. \"/hyprmoncfg-monitors.lua\")\n"
        )
        updated = H.inject_hyprland_hook(original)
        restored = H.remove_hyprland_hook(updated)
        self.assertNotIn("hypr.homing", restored)
        self.assertIn("hyprmoncfg", restored)
        self.assertIn("hypr.autostart", restored)

    def test_remove_reverses_append(self):
        original = 'require("hypr.bindings")\n'
        restored = H.remove_hyprland_hook(H.inject_hyprland_hook(original))
        self.assertEqual(restored, original)

    def test_remove_is_idempotent(self):
        original = 'require("hypr.bindings")\n'
        self.assertEqual(H.remove_hyprland_hook(original), original)

    def test_write_lua_does_not_touch_hyprland(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            hypr = home / ".config" / "hypr"
            hypr.mkdir(parents=True)
            hyprland = hypr / "hyprland.lua"
            original = 'require("hypr.bindings")\n'
            hyprland.write_text(original, encoding="utf-8")
            paths = H.Paths(
                home=home,
                assignments=home / ".config" / "omarchy" / "homing" / "assignments.json",
                lua=hypr / "homing.lua",
                hyprland_lua=hyprland,
            )
            H.write_lua(paths, H.empty_store())
            self.assertEqual(hyprland.read_text(encoding="utf-8"), original)
            self.assertTrue((hypr / "homing.lua").is_file())
            self.assertFalse(H.hyprland_hook_backup(hyprland).exists())

    def test_ensure_keeps_existing_homing_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hyprland.lua"
            bak = H.hyprland_hook_backup(path)
            path.write_text('require("hypr.bindings")\n', encoding="utf-8")
            bak.write_text("ORIGINAL\n", encoding="utf-8")
            self.assertTrue(H.ensure_hyprland_hook(path))
            self.assertEqual(bak.read_text(encoding="utf-8"), "ORIGINAL\n")
            self.assertIn("hypr.homing", path.read_text(encoding="utf-8"))

    def test_uninstall_files_removes_hook_and_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            hypr = home / ".config" / "hypr"
            homing_dir = home / ".config" / "omarchy" / "homing"
            hypr.mkdir(parents=True)
            homing_dir.mkdir(parents=True)
            hyprland = hypr / "hyprland.lua"
            hyprland.write_text('require("hypr.bindings")\n', encoding="utf-8")
            paths = H.Paths(
                home=home,
                assignments=homing_dir / "assignments.json",
                lua=hypr / "homing.lua",
                hyprland_lua=hyprland,
            )
            H.ensure_hyprland_hook(hyprland)
            H.write_lua(paths, H.empty_store())
            H.save_store(paths.assignments, H.empty_store())
            changed = H.uninstall_files(paths)
            self.assertNotIn("hypr.homing", hyprland.read_text(encoding="utf-8"))
            self.assertFalse(paths.lua.exists())
            self.assertFalse(paths.assignments.exists())
            self.assertFalse(homing_dir.exists())
            self.assertTrue(any(str(hyprland) == item for item in changed))


class FlagTests(unittest.TestCase):
    def test_equals_form(self):
        self.assertEqual(H.parse_flag("--profile-directory=Default --foo", "--profile-directory"), "Default")

    def test_profile_with_space_then_flag(self):
        cmdline = "/usr/lib/chromium/chromium --ozone-platform=wayland --profile-directory=Profile 1 --password-store=gnome"
        self.assertEqual(H.parse_flag(cmdline, "--profile-directory"), "Profile 1")

    def test_null_separated(self):
        cmdline = "/usr/lib/chromium/chromium\n--profile-directory=Profile 1\n--foo"
        self.assertEqual(H.parse_flag(cmdline, "--profile-directory"), "Profile 1")

    def test_user_data_dir(self):
        self.assertEqual(
            H.parse_flag("--user-data-dir=/tmp/chrome-work --bar", "--user-data-dir"),
            "/tmp/chrome-work",
        )


class WorkspaceTests(unittest.TestCase):
    def test_numeric(self):
        self.assertEqual(H.validate_workspace(" 7 "), "7")
        self.assertIsNone(H.validate_workspace("0"))
        self.assertIsNone(H.validate_workspace(""))

    def test_named_and_special(self):
        self.assertEqual(H.validate_workspace("mail"), "mail")
        self.assertEqual(H.validate_workspace("special:scratchpad"), "special:scratchpad")
        self.assertEqual(H.validate_workspace("name:code"), "name:code")
        self.assertIsNone(H.validate_workspace("bad workspace"))


def _deadline(fn, *args, timeout=2.0, **kwargs):
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(fn, *args, **kwargs).result(timeout=timeout)


class PersistTests(unittest.TestCase):
    def test_atomic_write_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "assignments.json"
            path.write_text('{"version": 1, "assignments": []}\n', encoding="utf-8")
            H.save_store(path, {"version": 1, "assignments": [{"id": "class:slack"}]})
            self.assertTrue(path.with_suffix(".json.bak").is_file())
            data = path.read_text(encoding="utf-8")
            self.assertIn("class:slack", data)
            self.assertFalse(path.with_name(path.name + ".tmp").exists())


class SafeIOTests(unittest.TestCase):
    def test_load_store_ignores_fifo(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "assignments.json"
            os.mkfifo(path)
            store = _deadline(H.load_store, path)
            self.assertEqual(store["assignments"], [])
            self.assertTrue(stat.S_ISFIFO(os.lstat(path).st_mode))

    def test_load_store_does_not_follow_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            victim = root / "victim.json"
            victim.write_text('{"version": 1, "assignments": [{"id": "class:secret"}]}\n', encoding="utf-8")
            path = root / "assignments.json"
            path.symlink_to(victim)
            store = _deadline(H.load_store, path)
            self.assertEqual(store["assignments"], [])
            self.assertEqual(victim.read_text(encoding="utf-8"), '{"version": 1, "assignments": [{"id": "class:secret"}]}\n')

    def test_load_store_rejects_oversized_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "assignments.json"
            path.write_text("x" * (H.MAX_TEXT_FILE_BYTES + 1), encoding="utf-8")
            store = H.load_store(path)
            self.assertEqual(store["assignments"], [])

    def test_atomic_write_ignores_planted_tmp_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "assignments.json"
            victim = root / "victim"
            victim.write_text("keep\n", encoding="utf-8")
            planted = path.with_name(path.name + ".tmp")
            planted.symlink_to(victim)
            _deadline(H.atomic_write, path, "safe\n")
            self.assertEqual(path.read_text(encoding="utf-8"), "safe\n")
            self.assertEqual(victim.read_text(encoding="utf-8"), "keep\n")
            self.assertTrue(planted.is_symlink())

    def test_atomic_write_ignores_planted_tmp_fifo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "assignments.json"
            planted = path.with_name(path.name + ".tmp")
            os.mkfifo(planted)
            _deadline(H.atomic_write, path, "safe\n")
            self.assertEqual(path.read_text(encoding="utf-8"), "safe\n")
            self.assertTrue(stat.S_ISFIFO(os.lstat(planted).st_mode))

    def test_backup_does_not_write_through_bak_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "assignments.json"
            path.write_text('{"version": 1, "assignments": []}\n', encoding="utf-8")
            victim = root / "victim"
            victim.write_text("keep\n", encoding="utf-8")
            bak = path.with_suffix(".json.bak")
            bak.symlink_to(victim)
            _deadline(H.save_store, path, {"version": 1, "assignments": [{"id": "class:slack"}]})
            self.assertEqual(victim.read_text(encoding="utf-8"), "keep\n")
            self.assertFalse(bak.is_symlink())
            self.assertIn("assignments", bak.read_text(encoding="utf-8"))

    def test_hook_backup_does_not_follow_dangling_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "hyprland.lua"
            path.write_text('require("hypr.bindings")\n', encoding="utf-8")
            victim = root / "victim"
            bak = H.hyprland_hook_backup(path)
            bak.symlink_to(victim)
            _deadline(H.backup_hyprland_hook, path)
            self.assertFalse(victim.exists())
            self.assertTrue(bak.is_symlink())

    def test_hook_backup_skips_planted_fifo(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hyprland.lua"
            path.write_text('require("hypr.bindings")\n', encoding="utf-8")
            bak = H.hyprland_hook_backup(path)
            os.mkfifo(bak)
            _deadline(H.backup_hyprland_hook, path)
            self.assertTrue(stat.S_ISFIFO(os.lstat(bak).st_mode))

    def test_ensure_does_not_follow_hyprland_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "dotfiles" / "hyprland.lua"
            target.parent.mkdir()
            original = 'require("hypr.bindings")\n'
            target.write_text(original, encoding="utf-8")
            path = root / "hyprland.lua"
            path.symlink_to(target)
            self.assertFalse(_deadline(H.ensure_hyprland_hook, path))
            self.assertEqual(target.read_text(encoding="utf-8"), original)
            self.assertTrue(path.is_symlink())

    def test_ensure_ignores_hyprland_fifo(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hyprland.lua"
            os.mkfifo(path)
            self.assertFalse(_deadline(H.ensure_hyprland_hook, path))
            self.assertTrue(stat.S_ISFIFO(os.lstat(path).st_mode))

    def test_local_state_does_not_follow_symlink_or_fifo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            victim = root / "real-state"
            victim.write_text('{"profile": {"info_cache": {"Work": {"name": "Work"}}}}\n', encoding="utf-8")
            linked = root / "linked"
            linked.mkdir()
            (linked / "Local State").symlink_to(victim)
            names = _deadline(H.profile_directories_from_local_state, linked)
            self.assertNotIn("Work", names)
            fifo_dir = root / "fifo"
            fifo_dir.mkdir()
            os.mkfifo(fifo_dir / "Local State")
            names = _deadline(H.profile_directories_from_local_state, fifo_dir)
            self.assertEqual(names["Default"], "Default")

    def test_uninstall_does_not_unlink_symlink_or_fifo(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            hypr = home / ".config" / "hypr"
            homing_dir = home / ".config" / "omarchy" / "homing"
            hypr.mkdir(parents=True)
            homing_dir.mkdir(parents=True)
            victim = home / "victim.lua"
            victim.write_text("keep\n", encoding="utf-8")
            lua = hypr / "homing.lua"
            lua.symlink_to(victim)
            fifo = homing_dir / "assignments.json"
            os.mkfifo(fifo)
            paths = H.Paths(
                home=home,
                assignments=fifo,
                lua=lua,
                hyprland_lua=hypr / "hyprland.lua",
            )
            changed = _deadline(H.uninstall_files, paths)
            self.assertTrue(lua.is_symlink())
            self.assertEqual(victim.read_text(encoding="utf-8"), "keep\n")
            self.assertTrue(stat.S_ISFIFO(os.lstat(fifo).st_mode))
            self.assertFalse(any(str(lua) == item or str(fifo) == item for item in changed))

    def test_exclusive_write_does_not_follow_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            victim = root / "victim"
            victim.write_text("keep\n", encoding="utf-8")
            path = root / "hyprland.lua.homing.bak"
            path.symlink_to(victim)
            with self.assertRaises(OSError):
                _deadline(H.exclusive_write, path, "overwrite\n")
            self.assertEqual(victim.read_text(encoding="utf-8"), "keep\n")
            self.assertTrue(path.is_symlink())

    def test_maybe_install_skips_symlink_hyprland(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            hypr = home / ".config" / "hypr"
            hypr.mkdir(parents=True)
            target = hypr / "real.lua"
            target.write_text('require("hypr.bindings")\n', encoding="utf-8")
            hyprland = hypr / "hyprland.lua"
            hyprland.symlink_to(target)
            paths = H.Paths(
                home=home,
                assignments=home / ".config" / "omarchy" / "homing" / "assignments.json",
                lua=hypr / "homing.lua",
                hyprland_lua=hyprland,
            )
            store = _deadline(H.maybe_install_hyprland_hook, paths, H.empty_store())
            self.assertEqual(store.get("hyprlandHook"), "unsafe-config")
            self.assertEqual(target.read_text(encoding="utf-8"), 'require("hypr.bindings")\n')
            self.assertTrue(hyprland.is_symlink())


class SubprocessTests(unittest.TestCase):
    def test_run_limited_captures_output(self):
        result = H.run_limited([sys.executable, "-c", "print('hello')"], timeout=5)
        self.assertIsNotNone(result)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "hello")

    def test_run_limited_passes_stdin(self):
        result = H.run_limited(
            [sys.executable, "-c", "import sys; print(sys.stdin.read(), end='')"],
            timeout=5,
            input_text="abc\n",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.stdout, "abc\n")

    def test_run_limited_times_out(self):
        started = time.monotonic()
        result = H.run_limited(["sleep", "30"], timeout=0.2)
        self.assertIsNone(result)
        self.assertLess(time.monotonic() - started, 5)

    def test_run_limited_caps_output(self):
        started = time.monotonic()
        result = H.run_limited(
            [sys.executable, "-c", "import sys; sys.stdout.write('x' * 5_000_000); sys.stdout.flush()"],
            timeout=5,
            max_output=64_000,
        )
        self.assertIsNone(result)
        self.assertLess(time.monotonic() - started, 5)

    def test_run_limited_missing_binary(self):
        self.assertIsNone(H.run_limited(["homing-no-such-command"], timeout=1))


if __name__ == "__main__":
    unittest.main()
