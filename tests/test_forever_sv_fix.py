import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

P = Path(__file__).parents[1] / "forever_sv_fix.py"
spec = importlib.util.spec_from_file_location("forever_sv_fix", P)
m = importlib.util.module_from_spec(spec)
sys.modules["forever_sv_fix"] = m
spec.loader.exec_module(m)


class Tests(unittest.TestCase):
    def test_inspect(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "Demo"
            d.mkdir()
            toc = d / "Demo.toc"
            toc.write_text(
                "## Interface: 16001\n"
                "## SavedVariables: DemoDB\n"
                "## SavedVariablesPerCharacter: DemoCharDB\n"
                "Demo.lua\n",
                encoding="utf-8",
            )
            info = m.inspect_toc(toc)
            self.assertTrue(info.account_saved)
            self.assertTrue(info.character_saved)

    def test_patch_both_modes_after_normal_code_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "Demo"
            d.mkdir()
            toc = d / "Demo.toc"
            toc.write_text(
                "## Interface: 16001\n"
                "## SavedVariables: DemoDB\n"
                "## SavedVariablesPerCharacter: DemoCharDB\n"
                "\n"
                "Lib.xml\n"
                "Demo.lua\n",
                encoding="utf-8",
            )

            m.patch_toc(toc, "Demo", True, True)
            lines = toc.read_text(encoding="utf-8").splitlines()
            a = lines.index(r"ForeverSVFixData\Demo.lua")
            c = lines.index("ForeverSVFixCharacter.lua")
            normal = lines.index("Demo.lua")
            self.assertLess(normal, a)
            self.assertLess(a, c)
            self.assertEqual(lines[-2:], [
                r"ForeverSVFixData\Demo.lua",
                "ForeverSVFixCharacter.lua",
            ])
            self.assertIn("## X-ForeverSVFix: 6", lines)

            m.unpatch_toc(toc, "Demo")
            restored = toc.read_text(encoding="utf-8")
            self.assertNotIn("ForeverSVFix", restored)
            self.assertIn("Lib.xml", restored)

    def test_load_saved_variables_first_keeps_restore_before_scripts(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "Demo"
            d.mkdir()
            toc = d / "Demo.toc"
            toc.write_text(
                "## Interface: 16001\n"
                "## LoadSavedVariablesFirst: 1\n"
                "## SavedVariables: DemoDB\n"
                "## SavedVariablesPerCharacter: DemoCharDB\n"
                "Demo.lua\n",
                encoding="utf-8",
            )

            m.patch_toc(toc, "Demo", True, True)
            lines = toc.read_text(encoding="utf-8").splitlines()
            a = lines.index(r"ForeverSVFixData\Demo.lua")
            c = lines.index("ForeverSVFixCharacter.lua")
            normal = lines.index("Demo.lua")
            self.assertLess(a, c)
            self.assertLess(c, normal)

    def test_v4_patch_is_reordered_to_post_script_restore(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "Demo"
            d.mkdir()
            toc = d / "Demo.toc"
            toc.write_text(
                "## Interface: 16001\n"
                "## SavedVariables: DemoDB\n"
                "## X-ForeverSVFix: 4\n"
                "ForeverSVFixData\\Demo.lua\n"
                "Demo.lua\n",
                encoding="utf-8",
            )

            m.patch_toc(toc, "Demo", True, False)
            lines = toc.read_text(encoding="utf-8").splitlines()
            normal = lines.index("Demo.lua")
            restore = lines.index(r"ForeverSVFixData\Demo.lua")
            self.assertLess(normal, restore)
            self.assertIn("## X-ForeverSVFix: 6", lines)
            self.assertNotIn("## X-ForeverSVFix: 4", lines)

    def test_v2_patch_is_migrated_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "Demo"
            d.mkdir()
            toc = d / "Demo.toc"
            toc.write_text(
                "## Interface: 16001\n"
                "## SavedVariables: DemoDB\n"
                "## X-ForeverSVFix: 2\n"
                "\n"
                "ForeverSVFixData\\Demo.lua\n"
                "Demo.lua\n",
                encoding="utf-8",
            )
            m.patch_toc(toc, "Demo", True, False)
            text = toc.read_text(encoding="utf-8")
            self.assertEqual(text.count("ForeverSVFixData\\Demo.lua"), 1)
            self.assertIn("## X-ForeverSVFix: 6", text)
            self.assertNotIn("## X-ForeverSVFix: 2", text)

    def test_character_store_discovery(self):
        with tempfile.TemporaryDirectory() as td:
            account = Path(td) / "123#1"
            (account / "SavedVariables").mkdir(parents=True)
            c = account / "70" / "Yawa-Wahala" / "SavedVariables"
            c.mkdir(parents=True)
            stores = m.character_stores(account)
            self.assertEqual(len(stores), 1)
            self.assertEqual(stores[0].realm_folder, "70")
            self.assertEqual(stores[0].character_folder, "Yawa-Wahala")

    def test_character_store_discovery_handles_split_forever_name(self):
        with tempfile.TemporaryDirectory() as td:
            account = Path(td) / "123#1"
            (account / "SavedVariables").mkdir(parents=True)
            c = account / "70" / "Nycterina" / "Sterngale" / "SavedVariables"
            c.mkdir(parents=True)
            stores = m.character_stores(account)
            self.assertEqual(len(stores), 1)
            self.assertEqual(stores[0].realm_folder, "70")
            self.assertEqual(stores[0].character_folder, "Nycterina/Sterngale")

    def test_windows_remove_link_recovers_normal_runtime_directory(self):
        old_system = m.platform.system
        try:
            with tempfile.TemporaryDirectory() as td:
                runtime = Path(td) / m.DATA_DIR
                runtime.mkdir()
                (runtime / "copied.lua").write_text("x=1\n", encoding="utf-8")
                m.platform.system = lambda: "Windows"
                m.remove_link(runtime)
                self.assertFalse(runtime.exists())
        finally:
            m.platform.system = old_system

    def test_windows_junction_creation_uses_tolerant_cmd_decoding(self):
        old_system = m.platform.system
        old_symlink = m.os.symlink
        old_run = m.subprocess.run
        seen = []
        try:
            m.platform.system = lambda: "Windows"

            def fail_symlink(*args, **kwargs):
                raise OSError("symlink unavailable")

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            def fake_run(*args, **kwargs):
                seen.append((args, kwargs))
                return Result()

            m.os.symlink = fail_symlink
            m.subprocess.run = fake_run

            with tempfile.TemporaryDirectory() as td:
                link = Path(td) / "link"
                target = Path(td) / "target"
                target.mkdir()
                self.assertEqual(m.make_dir_link(link, target), "junction")

            self.assertEqual(len(seen), 1)
            self.assertEqual(seen[0][1].get("errors"), "replace")
            self.assertTrue(seen[0][1].get("text"))
            self.assertTrue(seen[0][1].get("capture_output"))
        finally:
            m.platform.system = old_system
            m.os.symlink = old_symlink
            m.subprocess.run = old_run

    def test_windows_junction_removal_uses_tolerant_cmd_decoding(self):
        old_system = m.platform.system
        old_reparse = m.windows_reparse_point
        old_run = m.subprocess.run
        seen = []
        try:
            m.platform.system = lambda: "Windows"
            m.windows_reparse_point = lambda path: True

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            def fake_run(*args, **kwargs):
                seen.append((args, kwargs))
                return Result()

            m.subprocess.run = fake_run

            with tempfile.TemporaryDirectory() as td:
                junction = Path(td) / "junction"
                junction.mkdir()
                m.remove_link(junction)

            self.assertEqual(len(seen), 1)
            self.assertEqual(seen[0][1].get("errors"), "replace")
            self.assertTrue(seen[0][1].get("text"))
            self.assertTrue(seen[0][1].get("capture_output"))
        finally:
            m.platform.system = old_system
            m.windows_reparse_point = old_reparse
            m.subprocess.run = old_run

    def test_pc_helper_name_stable_and_unique(self):
        s1 = m.CharacterStore("70", "Yawa-Wahala", Path("/x/70/Yawa-Wahala/SavedVariables"))
        s2 = m.CharacterStore("71", "Other-Realm", Path("/x/71/Other-Realm/SavedVariables"))
        a = m.pc_helper_name("Demo", s1)
        b = m.pc_helper_name("Demo", s1)
        c = m.pc_helper_name("Demo", s2)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertTrue(a.startswith("ForeverSVFixPC_"))

    def test_generate_character_bootstrap(self):
        with tempfile.TemporaryDirectory() as td:
            addons = Path(td) / "AddOns"
            addon_dir = addons / "Demo"
            addon_dir.mkdir(parents=True)
            store_dir = Path(td) / "WTF" / "Account" / "A" / "70" / "Yawa-Wahala" / "SavedVariables"
            store_dir.mkdir(parents=True)
            (store_dir / "Demo.lua").write_text("DemoCharDB = {x=1}\n", encoding="utf-8")
            store = m.CharacterStore("70", "Yawa-Wahala", store_dir)

            entries, helpers = m.generate_char_bootstrap(addon_dir, "Demo", [store])
            self.assertEqual(len(entries), 1)
            self.assertEqual(len(helpers), 1)
            bootstrap = (addon_dir / m.CHAR_BOOTSTRAP).read_text(encoding="utf-8")
            self.assertIn("Yawa-Wahala", bootstrap)
            self.assertIn("C_AddOns.LoadAddOn", bootstrap)
            self.assertIn("local fullPlayer, realm", bootstrap)
            self.assertIn("local shortPlayer", bootstrap)
            self.assertIn('fullPlayer:match("^%S+")', bootstrap)
            self.assertIn("np:find(nc, 1, true) == 1", bootstrap)
            helper_toc = next(helpers[0].glob("*.toc")).read_text(encoding="utf-8")
            self.assertIn("## DefaultState: enabled", helper_toc)
            self.assertIn(r"Data\Demo.lua", helper_toc)
            self.assertTrue((helpers[0] / "Data" / "Demo.lua").is_file())

    def test_account_live_link_and_patch_on_fake_tree(self):
        if sys.platform.startswith("win"):
            self.skipTest("Temp Windows junction behavior covered in real CI/manual test.")
        with tempfile.TemporaryDirectory() as td:
            wow = Path(td) / "_classic_beta_"
            addon = wow / "Interface" / "AddOns" / "Demo"
            sv = wow / "WTF" / "Account" / "A#1" / "SavedVariables"
            addon.mkdir(parents=True)
            sv.mkdir(parents=True)
            (addon / "Demo.toc").write_text(
                "## Interface: 16001\n## SavedVariables: DemoDB\nDemo.lua\n",
                encoding="utf-8",
            )
            (addon / "Demo.lua").write_text("-- demo\n", encoding="utf-8")
            (sv / "Demo.lua").write_text("DemoDB={x=1}\n", encoding="utf-8")

            rc = m.install(wow, None)
            self.assertEqual(rc, 0)
            self.assertEqual((addon / m.DATA_DIR / "Demo.lua").read_text(), "DemoDB={x=1}\n")
            toc = (addon / "Demo.toc").read_text()
            self.assertIn(r"ForeverSVFixData\Demo.lua", toc)

            rc = m.doctor(wow, None)
            self.assertEqual(rc, 0)

            rc = m.uninstall(wow)
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.lexists(addon / m.DATA_DIR))
            self.assertNotIn("ForeverSVFix", (addon / "Demo.toc").read_text())

    def test_interface_filter(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "Demo"
            d.mkdir()

            cases = {
                "Demo.toc": "## Interface: 120100\n",
                "Demo_Camelot.toc": "## Interface: 16001\n",
                "Demo_Multi.toc": "## Interface: 20506, 16001, 120100\n",
                "Demo_Wrath.toc": "## Interface: 30405\n",
                "Demo_NoInterface.toc": "",
            }

            infos = {}
            for name, interface_line in cases.items():
                toc = d / name
                toc.write_text(
                    interface_line
                    + "## SavedVariables: DemoDB\n"
                    + "Demo.lua\n",
                    encoding="utf-8",
                )
                infos[name] = m.inspect_toc(toc)

            self.assertFalse(m.is_forever_toc(infos["Demo.toc"]))
            self.assertTrue(m.is_forever_toc(infos["Demo_Camelot.toc"]))
            self.assertTrue(m.is_forever_toc(infos["Demo_Multi.toc"]))
            self.assertFalse(m.is_forever_toc(infos["Demo_Wrath.toc"]))
            self.assertFalse(m.is_forever_toc(infos["Demo_NoInterface.toc"]))

    def test_reconcile_removes_stale_non_forever_patch(self):
        with tempfile.TemporaryDirectory() as td:
            addons = Path(td) / "AddOns"
            d = addons / "Demo"
            d.mkdir(parents=True)

            retail = d / "Demo.toc"
            retail.write_text(
                "## Interface: 120100\n"
                "## SavedVariables: DemoDB\n"
                "## X-ForeverSVFix: 4\n"
                "ForeverSVFixData\\Demo.lua\n"
                "Demo.lua\n",
                encoding="utf-8",
            )

            forever = d / "Demo_Camelot.toc"
            forever.write_text(
                "## Interface: 16001\n"
                "## SavedVariables: DemoDB\n"
                "Demo.lua\n",
                encoding="utf-8",
            )

            cleaned = m.reconcile_old_patches(
                addons,
                {forever},
                {d},
            )
            self.assertEqual(cleaned, 1)
            self.assertNotIn("ForeverSVFix", retail.read_text(encoding="utf-8"))

    def test_patch_metadata_only_account_toc(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "BagBrother"
            d.mkdir()
            toc = d / "BagBrother.toc"
            toc.write_text(
                "## Interface: 16001\n"
                "## Title: BagBrother\n"
                "## SavedVariables: BrotherBags\n",
                encoding="utf-8",
            )

            self.assertTrue(m.patch_toc(toc, "BagBrother", True, False))
            lines = toc.read_text(encoding="utf-8").splitlines()
            self.assertIn("## X-ForeverSVFix: 6", lines)
            self.assertIn(r"ForeverSVFixData\BagBrother.lua", lines)
            self.assertEqual(lines[-1], r"ForeverSVFixData\BagBrother.lua")

            self.assertTrue(m.unpatch_toc(toc, "BagBrother"))
            restored = toc.read_text(encoding="utf-8")
            self.assertNotIn("ForeverSVFix", restored)
            self.assertIn("## SavedVariables: BrotherBags", restored)

    def test_patch_metadata_only_mixed_toc(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "MetaAddon"
            d.mkdir()
            toc = d / "MetaAddon.toc"
            toc.write_text(
                "## Interface: 16001\n"
                "## SavedVariables: MetaDB\n"
                "## SavedVariablesPerCharacter: MetaCharDB\n",
                encoding="utf-8",
            )

            m.patch_toc(toc, "MetaAddon", True, True)
            lines = toc.read_text(encoding="utf-8").splitlines()
            ai = lines.index(r"ForeverSVFixData\MetaAddon.lua")
            ci = lines.index("ForeverSVFixCharacter.lua")
            self.assertLess(ai, ci)
            self.assertEqual(lines[-2:], [
                r"ForeverSVFixData\MetaAddon.lua",
                "ForeverSVFixCharacter.lua",
            ])

    def test_parser_allows_interactive_without_wow(self):
        args = m.build_parser().parse_args([])
        self.assertIsNone(args.command)
        self.assertIsNone(args.wow)

    def test_known_candidate_filter_ignores_invalid_paths(self):
        # This primarily guards against auto-detection ever treating arbitrary
        # existing directories as WoW installs.
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(m.FixError):
                m.validate_wow(Path(td))

    def test_status_not_installed_uses_current_version(self):
        with tempfile.TemporaryDirectory() as td:
            wow = Path(td)
            from io import StringIO
            from contextlib import redirect_stdout
            out = StringIO()
            with redirect_stdout(out):
                rc = m.status(wow)
            self.assertEqual(rc, 1)
            self.assertIn(m.VERSION, out.getvalue())
            self.assertNotIn("v0.3 is not installed", out.getvalue())


    def test_legacy_ellesmere_migration_is_explicit_backed_up_and_post_script(self):
        if sys.platform.startswith("win"):
            self.skipTest("Temp Windows junction behavior covered in real CI/manual test.")

        with tempfile.TemporaryDirectory() as td:
            wow = Path(td) / "_classic_beta_"
            addon = wow / "Interface" / "AddOns" / "EllesmereUI"
            sv = wow / "WTF" / "Account" / "A#1" / "SavedVariables"
            addon.mkdir(parents=True)
            sv.mkdir(parents=True)

            toc = addon / "EllesmereUI.toc"
            toc.write_text(
                "## Interface: 120100, 16001\n"
                "## SavedVariables: EllesmereUIDB\n"
                "## X-ForeverSVFix: 5\n"
                "ForeverSVFixData\\EllesmereUI.lua\n"
                "EllesmereUI_ClientGate.lua\n"
                "EllesmereUI_Lite.lua\n"
                "ForeverSVFixEllesmereUI.lua\n"
                "EllesmereUI_Profiles.lua\n"
                "EllesmereUI_ForeverNotice.lua\n",
                encoding="utf-8",
            )
            shim = addon / m.ELLESMERE_COMPAT
            shim.write_text(
                "if EllesmereUI then EllesmereUI.FOREVER_SV_BUG = false end\n",
                encoding="utf-8",
            )
            (sv / "EllesmereUI.lua").write_text(
                "EllesmereUIDB={profiles={}}\n",
                encoding="utf-8",
            )
            m.save_state(
                wow,
                {
                    "version": "1.0.3",
                    "account": "A#1",
                    "patched": [
                        {
                            "toc": str(toc),
                            "addon": "EllesmereUI",
                            "account": True,
                            "per_character": [],
                        }
                    ],
                    "linked_account_dirs": {},
                    "generated_pc_dirs": [],
                    "char_bootstraps": [],
                    "pc_meta": {},
                    "ellesmere_compat_files": [str(shim)],
                },
            )

            before_toc = toc.read_text(encoding="utf-8")
            before_shim = shim.read_text(encoding="utf-8")

            with self.assertRaises(m.FixError):
                m.install(wow, None)

            self.assertEqual(toc.read_text(encoding="utf-8"), before_toc)
            self.assertEqual(shim.read_text(encoding="utf-8"), before_shim)

            self.assertEqual(
                m.install(
                    wow,
                    None,
                    allow_legacy_ellesmere_cleanup=True,
                ),
                0,
            )

            updated = toc.read_text(encoding="utf-8")
            lines = updated.splitlines()
            self.assertIn("## X-ForeverSVFix: 6", lines)
            self.assertNotIn("## X-ForeverSVFix: 5", lines)
            self.assertNotIn(m.ELLESMERE_COMPAT, updated)
            self.assertFalse(shim.exists())
            self.assertEqual(updated.count(r"ForeverSVFixData\EllesmereUI.lua"), 1)

            profiles = lines.index("EllesmereUI_Profiles.lua")
            restore = lines.index(r"ForeverSVFixData\EllesmereUI.lua")
            self.assertLess(profiles, restore)

            state = m.load_state(wow)
            self.assertNotIn("ellesmere_compat_files", state)
            self.assertEqual(state["version"], "1.0.4")

            backup = Path(state["backup"])
            self.assertTrue(
                (
                    backup
                    / "legacy-ellesmere"
                    / "runtime"
                    / "EllesmereUI"
                    / m.ELLESMERE_COMPAT
                ).is_file()
            )
            self.assertTrue(
                (
                    backup
                    / "legacy-ellesmere"
                    / "tocs"
                    / "EllesmereUI"
                    / "EllesmereUI.toc"
                ).is_file()
            )
            self.assertEqual(m.doctor(wow, None), 0)

    def test_legacy_ellesmere_state_path_outside_addons_is_never_deleted(self):
        with tempfile.TemporaryDirectory() as td:
            wow = Path(td) / "_classic_beta_"
            (wow / "Interface" / "AddOns").mkdir(parents=True)
            (wow / "WTF" / "Account" / "A#1" / "SavedVariables").mkdir(parents=True)

            outside = Path(td) / m.ELLESMERE_COMPAT
            outside.write_text("do not delete\n", encoding="utf-8")
            m.save_state(
                wow,
                {
                    "version": "1.0.3",
                    "account": "A#1",
                    "patched": [],
                    "linked_account_dirs": {},
                    "generated_pc_dirs": [],
                    "ellesmere_compat_files": [str(outside)],
                },
            )

            legacy = m.legacy_ellesmere_artifacts(wow)
            self.assertTrue(m.legacy_ellesmere_present(legacy))
            m.cleanup_legacy_ellesmere(wow, legacy)
            self.assertTrue(outside.is_file())

    def test_status_uses_current_state_schema(self):
        with tempfile.TemporaryDirectory() as td:
            wow = Path(td)
            (wow / "Interface" / "AddOns").mkdir(parents=True)
            m.save_state(wow, {
                "version": m.VERSION,
                "account": "A#1",
                "patched": [{"toc": "one"}, {"toc": "two"}],
                "linked_account_dirs": {"a": "symlink"},
                "generated_pc_dirs": ["pc1", "pc2", "pc3"],
            })
            from io import StringIO
            from contextlib import redirect_stdout
            out = StringIO()
            with redirect_stdout(out):
                rc = m.status(wow)
            self.assertEqual(rc, 0)
            text = out.getvalue()
            self.assertIn("Patched TOCs:       2", text)
            self.assertIn("Account links:      1", text)
            self.assertIn("Character helpers:  3", text)
            self.assertNotIn("EllesmereUI fix:", text)


    def test_version_key_orders_release_candidates_and_stable(self):
        self.assertLess(m.version_key("0.4.0-rc9"), m.version_key("0.4.0-rc10"))
        self.assertLess(m.version_key("v0.4.0-rc10"), m.version_key("0.4.0"))
        self.assertLess(m.version_key("0.4.0"), m.version_key("0.4.1-rc1"))
        self.assertIsNone(m.version_key("nightly"))

    def test_select_latest_release_includes_prereleases_and_skips_drafts(self):
        releases = [
            {"tag_name": "v0.4.0-rc9", "draft": False, "prerelease": True},
            {"tag_name": "v0.4.0-rc10", "draft": False, "prerelease": True},
            {"tag_name": "v9.9.9", "draft": True, "prerelease": False},
            {"tag_name": "nightly", "draft": False, "prerelease": True},
        ]
        latest = m.select_latest_release(releases)
        self.assertEqual(latest["tag_name"], "v0.4.0-rc10")

    def test_update_available_uses_current_version(self):
        self.assertFalse(m.update_available(m.VERSION))
        self.assertFalse(m.update_available("v0.4.0-rc9"))
        self.assertFalse(m.update_available("v1.0.0"))
        self.assertFalse(m.update_available("v1.0.3"))
        self.assertFalse(m.update_available("v1.0.4-rc1"))
        self.assertTrue(m.update_available("v1.0.5-rc1"))

    def test_https_context_prefers_certifi_bundle(self):
        old_certifi = m.certifi
        old_create = m.ssl.create_default_context
        seen = []

        class FakeCertifi:
            @staticmethod
            def where():
                return "/tmp/fake-certifi.pem"

        try:
            m.certifi = FakeCertifi
            m.ssl.create_default_context = lambda **kwargs: seen.append(kwargs) or object()
            m.https_context()
            self.assertEqual(seen, [{"cafile": "/tmp/fake-certifi.pem"}])
        finally:
            m.certifi = old_certifi
            m.ssl.create_default_context = old_create

    def test_https_context_falls_back_without_certifi(self):
        old_certifi = m.certifi
        old_create = m.ssl.create_default_context
        seen = []
        try:
            m.certifi = None
            m.ssl.create_default_context = lambda **kwargs: seen.append(kwargs) or object()
            m.https_context()
            self.assertEqual(seen, [{}])
        finally:
            m.certifi = old_certifi
            m.ssl.create_default_context = old_create

    def test_cached_update_check_does_not_touch_network(self):
        old_fetch = m.fetch_latest_release
        old_config_dir = m.config_dir
        try:
            with tempfile.TemporaryDirectory() as td:
                m.config_dir = lambda: Path(td)
                m.fetch_latest_release = lambda: self.fail("network should not be called")
                cfg = {
                    "update_check": {
                        "last_checked": int(m.time.time()),
                        "latest_tag": "v1.0.5-rc1",
                        "latest_url": "https://github.com/nobewayo/ForeverSVFix/releases/tag/v1.0.5-rc1",
                    }
                }
                result = m.check_for_update(cfg, force=False)
                self.assertTrue(result["from_cache"])
                self.assertTrue(result["available"])
        finally:
            m.fetch_latest_release = old_fetch
            m.config_dir = old_config_dir


    def test_doctor_show_status_combines_health_and_status(self):
        from contextlib import redirect_stdout
        from io import StringIO

        with tempfile.TemporaryDirectory() as td:
            wow = Path(td) / "_classic_beta_"
            (wow / "Interface" / "AddOns").mkdir(parents=True)
            (wow / "WTF" / "Account" / "A#1" / "SavedVariables").mkdir(parents=True)

            m.save_state(wow, {
                "version": m.VERSION,
                "account": "A#1",
                "patched": [],
                "linked_account_dirs": {},
                "generated_pc_dirs": [],
            })

            out = StringIO()
            with redirect_stdout(out):
                rc = m.doctor(wow, "A#1", show_status=True)

            self.assertEqual(rc, 0)
            text = out.getvalue()
            self.assertIn("installation check", text)
            self.assertIn("Installation:         OK", text)
            self.assertIn("Installed version:    " + m.VERSION, text)
            self.assertIn("Patched TOCs:         0", text)
            self.assertIn("Account links:        0", text)
            self.assertIn("Character helpers:    0", text)
            self.assertIn("No repair needed.", text)


if __name__ == "__main__":
    unittest.main()
