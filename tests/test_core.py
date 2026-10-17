import json
import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from keystone import core


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / "keystone"
        core.initialize(self.data, "Owner")
        for child in core.vault_path(self.data).iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    def save(self, **changes):
        payload = {"id": "restart", "title": "Restart the service", "type": "runbook",
                   "body": "Check the deployment logs before restarting.", "tags": ["service"]}
        payload.update(changes)
        return core.save_document(self.data, payload)

    def workflow(self, steps, status="verified"):
        path = core.vault_path(self.data) / "Workflows/check.json"
        core.atomic_write(path, json.dumps({"id": "check", "title": "Check service", "status": status, "steps": steps}))

    def test_refuses_existing_vault_and_preserves_content(self):
        other = Path(self.temp.name) / "foreign"
        (other / "vault/.obsidian").mkdir(parents=True)
        note = other / "vault/personal.md"
        note.write_text("Private personal note")
        with self.assertRaises(core.KeystoneError):
            core.initialize(other)
        self.assertEqual(note.read_text(), "Private personal note")
        self.assertFalse((other / "config.json").exists())

    def test_init_is_idempotent(self):
        document = self.save()
        core.initialize(self.data, "Other")
        self.assertEqual(core.load_config(self.data)["owner"], "Owner")
        self.assertEqual(core.get_document(self.data, document["id"])["revision"], document["revision"])

    def test_read_write_search_and_reader_publication_boundary(self):
        draft = self.save()
        self.assertEqual(core.list_documents(self.data, "reader"), [])
        self.assertEqual(len(core.list_documents(self.data, query="deployment service")), 1)
        verified = self.save(status="verified", revision=draft["revision"])
        self.assertEqual(core.list_documents(self.data, "reader")[0]["id"], "restart")
        self.assertNotEqual(verified["revision"], draft["revision"])
        self.assertTrue(verified["verified"])

    def test_author_edits_demote_verification_and_cannot_impersonate(self):
        document = self.save(status="verified")
        payload = dict(document, body="Updated procedure", status="draft", author="Owner")
        updated = core.save_document(self.data, payload, "author", "Contributor")
        self.assertEqual(updated["author"], "Contributor")
        self.assertEqual(updated["verified"], "")
        self.assertEqual(core.list_documents(self.data, "reader"), [])
        with self.assertRaises(core.KeystoneError) as error:
            core.save_document(self.data, dict(updated, status="verified"), "author", "Contributor")
        self.assertEqual(error.exception.status, 403)
        with self.assertRaises(core.KeystoneError):
            core.save_document(self.data, {"title": "No"}, "reader", "Reader")

    def test_conflict_protection_includes_external_obsidian_edits(self):
        original = self.save()
        path = core.vault_path(self.data) / original["path"]
        path.write_text(path.read_text() + "\nEdited in Obsidian.\n")
        with self.assertRaises(core.KeystoneError) as error:
            self.save(revision=original["revision"])
        self.assertEqual(error.exception.status, 409)
        self.assertIn("Edited in Obsidian", path.read_text())

    def test_two_concurrent_authors_cannot_overwrite_each_other(self):
        original = self.save()
        def attempt(name):
            try:
                return self.save(revision=original["revision"], body=name)["body"]
            except core.KeystoneError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["Author one", "Author two"]))
        self.assertEqual(results.count(409), 1)

    def test_path_and_symlink_escape_are_rejected(self):
        for document_id in ["../escape", "/tmp/escape", "a/b", ".."]:
            with self.assertRaises(core.KeystoneError):
                self.save(id=document_id)
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        link = core.vault_path(self.data) / "Runbooks"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symbolic links unavailable")
        with self.assertRaises(core.KeystoneError):
            self.save()
        self.assertEqual(list(outside.iterdir()), [])

    def test_context_references_round_trip_and_template_exclusion(self):
        document = self.save(type="context", sources=["https://example.test/task/1"], related_ids=["setup"])
        self.assertEqual(document["sources"], ["https://example.test/task/1"])
        self.assertEqual(document["related_ids"], ["setup"])
        core.atomic_write(core.vault_path(self.data) / "Templates/Untitled.md", "# Template")
        self.assertEqual(len(core.list_documents(self.data)), 1)

    def test_yaml_subset_reads_obsidian_properties(self):
        metadata, body = core.parse_markdown("---\ntitle: 'A useful note'\ntags:\n  - cloud\n  - deployment\nexample: true\n---\n\nContent")
        self.assertEqual(metadata["tags"], ["cloud", "deployment"])
        self.assertIs(metadata["example"], True)
        self.assertEqual(body, "Content")

    def test_token_secret_never_persisted_or_returned_in_settings(self):
        token = core.issue_token(self.data, "author", "Engineer")
        self.assertEqual(core.authenticate(self.data, token), {"role": "author", "author": "Engineer"})
        self.assertIsNone(core.authenticate(self.data, token + "bad"))
        self.assertNotIn(token, (self.data / "config.json").read_text())
        self.assertNotIn("tokens", core.public_settings(self.data, "owner"))
        self.assertEqual(core.public_settings(self.data, "reader"), {})

    def test_backup_configuration_cannot_target_vault(self):
        with self.assertRaises(core.KeystoneError):
            core.update_settings(self.data, {"backup": {"provider": "local", "destination": str(core.vault_path(self.data) / "backups")}})
        with self.assertRaises(core.KeystoneError):
            core.update_settings(self.data, {"backup": {"provider": "rclone", "remote": "--malicious"}})

    def test_workflow_topological_order_and_reader_visibility(self):
        self.save(status="verified")
        self.workflow([
            {"id": "verify", "document_id": "restart", "depends_on": ["inspect"], "requires_approval": True},
            {"id": "inspect", "document_id": "restart", "depends_on": []},
        ])
        plan = core.workflow_plan(self.data, "check", "reader")
        self.assertEqual([step["id"] for step in plan["steps"]], ["inspect", "verify"])
        self.assertEqual(plan["execution"], "plan-only")
        original = core.get_document(self.data, "restart")
        self.save(status="draft", revision=original["revision"])
        self.assertEqual(core.list_workflows(self.data, "reader"), [])

    def test_workflow_rejects_cycles_missing_docs_and_dependencies(self):
        self.save()
        bad_steps = [
            [{"id": "a", "document_id": "restart", "depends_on": ["b"]}, {"id": "b", "document_id": "restart", "depends_on": ["a"]}],
            [{"id": "a", "document_id": "missing"}],
            [{"id": "a", "document_id": "restart", "depends_on": ["missing"]}],
            [{"id": "a", "document_id": "restart"}, {"id": "a", "document_id": "restart"}],
        ]
        for steps in bad_steps:
            with self.subTest(steps=steps):
                self.workflow(steps)
                with self.assertRaises(core.KeystoneError):
                    core.workflow_plan(self.data, "check")


if __name__ == "__main__":
    unittest.main()
