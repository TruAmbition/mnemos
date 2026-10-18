import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from mnemos import core
from mnemos.handoff import build_pack, skills_archive
from mnemos.__main__ import main


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / "data"
        core.initialize(self.data)
        self.note = core.save_document(self.data, {"id": "enterprise-cache", "title": "Enterprise cache",
            "body": "Cache repair " * 900, "related_ids": ["example-first-capture"], "sources": ["local:test"]})

    def test_bounded_pack_keeps_revisions_and_omits_full_bodies_and_config(self):
        token = core.issue_token(self.data, "owner", "Example")
        pack = build_pack(self.data, "enterprise cache", 500)
        self.assertLessEqual(len(pack["recall"]["context"]), 500)
        self.assertEqual(pack["mode"], "bounded-excerpts")
        self.assertTrue(pack["documents"])
        source = next(doc for doc in pack["documents"] if doc["id"] == self.note["id"])
        self.assertEqual(source["revision"], self.note["revision"])
        self.assertNotIn("body", source)
        self.assertNotIn(token, json.dumps(pack))
        self.assertNotIn("tokens", pack)

    def test_explicit_full_document_selection_is_limited_and_access_filtered(self):
        pack = build_pack(self.data, "enterprise", document_ids=[self.note["id"]])
        self.assertEqual(pack["documents"][0]["body"], self.note["body"])
        with self.assertRaises(core.MnemosError):
            build_pack(self.data, "enterprise", role="reader", document_ids=[self.note["id"]])
        huge = core.save_document(self.data, {"id": "huge", "title": "Huge", "body": "x" * 220000})
        with self.assertRaisesRegex(core.MnemosError, "200 KB"):
            build_pack(self.data, "huge", document_ids=[huge["id"]])

    def test_cli_pack_and_skills_export_work_without_network(self):
        target = Path(self.temp.name) / "pack.json"
        self.assertEqual(main(["handoff", "enterprise", "--data", str(self.data), "--output", str(target)]), 0)
        self.assertEqual(json.loads(target.read_text())["format"], "mnemos-context-pack-v1")
        archive = Path(self.temp.name) / "skills.zip"
        self.assertEqual(main(["skills-export", "--data", str(self.data / "absent"), "--output", str(archive)]), 0)
        with zipfile.ZipFile(archive) as bundle:
            self.assertIn("mnemos-capture/SKILL.md", bundle.namelist())
            self.assertFalse(any("data/" in name or "config.json" in name for name in bundle.namelist()))

    def test_skill_archive_refuses_symlink_and_ignores_unrelated_files(self):
        root = Path(self.temp.name) / "fake"
        skill = root / "skills/mnemos-test"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("Skill instructions")
        (skill / "secret.txt").write_text("Do not include")
        with patch.object(core, "ROOT", root):
            with zipfile.ZipFile(io.BytesIO(skills_archive())) as bundle:
                self.assertEqual(bundle.namelist(), ["mnemos-test/SKILL.md"])
            (skill / "references").symlink_to(root, target_is_directory=True)
            with self.assertRaises(core.MnemosError):
                skills_archive()

    def test_related_links_use_real_paths_and_refresh_without_duplicates(self):
        target = core.get_document(self.data, "example-first-capture")
        self.assertIn("[[Runbooks/first-capture|", self.note["body"])
        self.assertNotIn("[[example-first-capture", self.note["body"])
        updated = core.save_document(self.data, dict(self.note, body=self.note["body"] + "\n\n[[manual-link]]"))
        self.assertEqual(updated["body"].count("<!-- mnemos:related:start -->"), 1)
        self.assertIn("[[manual-link]]", updated["body"])
        updated = core.save_document(self.data, dict(updated, related_ids=[]))
        self.assertNotIn("mnemos:related", updated["body"])
        self.assertIn("[[manual-link]]", updated["body"])
        self.assertEqual(core.get_document(self.data, target["id"])["revision"], target["revision"])


if __name__ == "__main__":
    unittest.main()
