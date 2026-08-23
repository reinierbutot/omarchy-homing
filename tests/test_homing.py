#!/usr/bin/python3
import importlib.machinery
import importlib.util
import sys
import tempfile
import unittest
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
        self.assertIn("/home/reinier/.config/chromium", lua)

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


if __name__ == "__main__":
    unittest.main()
