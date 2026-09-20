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

    def test_patch_both_modes_before_normal_code(self):
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
            n = lines.index("Lib.xml")
            self.assertLess(a, n)
            self.assertLess(c, n)
            self.assertLess(a, c)
            self.assertIn("## X-ForeverSVFix: 4", lines)

            m.unpatch_toc(toc, "Demo")
            restored = toc.read_text(encoding="utf-8")
            self.assertNotIn("ForeverSVFix", restored)
            self.assertIn("Lib.xml", restored)

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
            self.assertIn("## X-ForeverSVFix: 4", text)
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
            helper_toc = next(helpers[0].glob("*.toc")).read_text(encoding="utf-8")
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
            self.assertIn("## X-ForeverSVFix: 4", lines)
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


    def test_ellesmere_compat_patch_loads_immediately_after_lite(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "EllesmereUI"
            d.mkdir()
            toc = d / "EllesmereUI.toc"
            toc.write_text(
                "## Interface: 120100, 16001\n"
                "## SavedVariables: EllesmereUIDB\n"
                "EllesmereUI_ClientGate.lua\n"
                "EllesmereUI_Lite.lua\n"
                "EllesmereUI_Profiles.lua\n"
                "EllesmereUI_ForeverNotice.lua\n",
                encoding="utf-8",
            )
            self.assertTrue(m.ellesmere_profile_compat_supported(toc))
            m.generate_ellesmere_compat(d)
            m.patch_toc(toc, "EllesmereUI", True, False, True)
            lines = toc.read_text(encoding="utf-8").splitlines()
            live = lines.index(r"ForeverSVFixData\EllesmereUI.lua")
            gate = lines.index("EllesmereUI_ClientGate.lua")
            lite = lines.index("EllesmereUI_Lite.lua")
            compat = lines.index(m.ELLESMERE_COMPAT)
            profiles = lines.index("EllesmereUI_Profiles.lua")
            self.assertLess(live, gate)
            self.assertEqual(compat, lite + 1)
            self.assertLess(compat, profiles)
            shim = (d / m.ELLESMERE_COMPAT).read_text(encoding="utf-8")
            self.assertIn("EllesmereUI.FOREVER_SV_BUG = false", shim)
            self.assertNotIn("EllesmereUI.IS_FOREVER = false", shim)

    def test_ellesmere_compat_fails_closed_on_unknown_layout(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "EllesmereUI"
            d.mkdir()
            toc = d / "EllesmereUI.toc"
            toc.write_text(
                "## Interface: 16001\n"
                "## SavedVariables: EllesmereUIDB\n"
                "SomeFutureLoader.lua\n",
                encoding="utf-8",
            )
            self.assertFalse(m.ellesmere_profile_compat_supported(toc))

    def test_ellesmere_install_doctor_and_uninstall(self):
        if sys.platform.startswith("win"):
            self.skipTest("Temp Windows junction behavior covered in real CI/manual test.")
        with tempfile.TemporaryDirectory() as td:
            wow = Path(td) / "_classic_beta_"
            addon = wow / "Interface" / "AddOns" / "EllesmereUI"
            sv = wow / "WTF" / "Account" / "A#1" / "SavedVariables"
            addon.mkdir(parents=True)
            sv.mkdir(parents=True)
            (addon / "EllesmereUI.toc").write_text(
                "## Interface: 120100, 16001\n"
                "## SavedVariables: EllesmereUIDB\n"
                "EllesmereUI_ClientGate.lua\n"
                "EllesmereUI_Lite.lua\n"
                "EllesmereUI_Profiles.lua\n"
                "EllesmereUI_ForeverNotice.lua\n",
                encoding="utf-8",
            )
            (sv / "EllesmereUI.lua").write_text("EllesmereUIDB={profiles={}}\n", encoding="utf-8")

            self.assertEqual(m.install(wow, None), 0)
            toc = (addon / "EllesmereUI.toc").read_text(encoding="utf-8")
            self.assertIn(m.ELLESMERE_COMPAT, toc)
            self.assertTrue((addon / m.ELLESMERE_COMPAT).is_file())
            self.assertEqual(m.doctor(wow, None), 0)

            (addon / m.ELLESMERE_COMPAT).unlink()
            self.assertEqual(m.doctor(wow, None), 1)
            m.install(wow, None)
            self.assertEqual(m.doctor(wow, None), 0)

            self.assertEqual(m.uninstall(wow), 0)
            self.assertFalse((addon / m.ELLESMERE_COMPAT).exists())
            self.assertNotIn("ForeverSVFix", (addon / "EllesmereUI.toc").read_text(encoding="utf-8"))

    def test_status_uses_current_state_schema(self):
        with tempfile.TemporaryDirectory() as td:
            wow = Path(td)
            m.save_state(wow, {
                "version": m.VERSION,
                "account": "A#1",
                "patched": [{"toc": "one"}, {"toc": "two"}],
                "linked_account_dirs": {"a": "symlink"},
                "generated_pc_dirs": ["pc1", "pc2", "pc3"],
                "ellesmere_compat_files": ["compat"],
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
            self.assertIn("EllesmereUI fix:    1", text)


if __name__ == "__main__":
    unittest.main()
