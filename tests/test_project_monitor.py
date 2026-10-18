"""Exercise actual local Git commits, opt-in persistence, and service lifecycle."""
import http.client
import json
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mnemos import core, projects
from mnemos.project_monitor import ProjectMonitor
from mnemos.server import MnemosServer
import test_projects


@unittest.skipUnless(test_projects.shutil.which('git'), 'Git is required for local project tests')
class AutomaticProjectTests(unittest.TestCase):
    setUp = test_projects.ProjectTests.setUp
    git = test_projects.ProjectTests.git
    write = test_projects.ProjectTests.write
    commit = test_projects.ProjectTests.commit
    register = test_projects.ProjectTests.register

    def current(self):
        return projects.list_projects(self.data)['projects'][0]

    def monitor(self, **settings):
        server = SimpleNamespace(data_path=self.data, workspace_lock=threading.RLock(),
                                 setup_enabled=True, stopping=False, installation_file=None,
                                 assert_selection_current=lambda: None)
        server.__dict__.update(settings)
        return ProjectMonitor(server, interval=.03)

    def test_default_off_and_strict_opt_in(self):
        project = self.register()
        self.assertIs(project['auto_refresh'], False)
        with patch.object(projects, '_git') as git:
            self.assertEqual(projects.refresh_if_changed(self.data, project['id'])['state'], 'off')
            git.assert_not_called()
        for value in ['true', 1, None, []]:
            with self.assertRaises(core.MnemosError):
                projects.set_automatic(self.data, {**project, 'auto_refresh': value})
        self.assertIs(self.current()['auto_refresh'], False)

    def test_initial_snapshot_new_commit_and_unchanged_dedup(self):
        project = self.register(auto_refresh=True)
        monitor = self.monitor()
        monitor.scan_once()
        first = self.current()
        document = core.get_document(self.data, first['last_refresh']['document_id'])
        edited = core.save_document(self.data, {**document, 'body': 'Human review preserved.'})
        monitor.scan_once()
        self.assertEqual(self.current()['last_refresh'], first['last_refresh'])
        self.assertEqual(core.get_document(self.data, document['id'])['revision'], edited['revision'])
        self.write('README.md', '# Nimbus\n\nA new committed procedure.\n')
        commit = self.commit()
        monitor.scan_once()
        latest = self.current()
        self.assertEqual(latest['last_refresh']['commit'], commit)
        self.assertNotEqual(latest['last_refresh']['document_id'], document['id'])
        self.assertEqual(latest['revision'], project['revision'])
        self.assertEqual(core.get_document(self.data, document['id'])['body'], edited['body'])
        self.assertEqual(monitor.overview(projects.list_projects(self.data))['projects'][0]['automatic_status']['state'], 'captured')

    def test_background_refresh_preserves_open_settings_revision(self):
        project = self.register(auto_refresh=True)
        self.monitor().scan_once()
        saved = projects.save_project(self.data, {**project, 'include': ['README.md', 'src/*.py']})['project']
        self.assertIn('last_refresh', saved)
        self.monitor().scan_once()
        self.assertEqual(self.current()['last_refresh']['source_count'], 2)
        with self.assertRaises(core.MnemosError) as error:
            projects.set_automatic(self.data, {**project, 'auto_refresh': False})
        self.assertEqual(error.exception.status, 409)

    def test_disable_missing_repository_and_persist_across_monitors(self):
        project = self.register(auto_refresh=True)
        self.repo.rename(self.root / 'moved')
        monitor = self.monitor()
        monitor.scan_once()
        self.assertEqual(monitor.checks[(str(self.data), project['id'])]['state'], 'error')
        projects.set_automatic(self.data, {**project, 'auto_refresh': False})
        with patch.object(projects, '_git') as git:
            self.monitor().scan_once()
            git.assert_not_called()
        self.assertNotIn('last_refresh', self.current())

    def test_two_monitors_deduplicate_same_commit(self):
        self.register(auto_refresh=True)
        before = len(core.list_documents(self.data))
        workers = [threading.Thread(target=self.monitor().scan_once) for _ in range(2)]
        for worker in workers: worker.start()
        for worker in workers: worker.join(10)
        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(len(core.list_documents(self.data)), before + 1)

    def test_guards_and_stop_prevent_inspection(self):
        self.register(auto_refresh=True)
        stale = self.monitor(assert_selection_current=lambda: (_ for _ in ()).throw(core.MnemosError('changed')))
        with patch.object(projects, 'refresh_if_changed') as refresh:
            stale.scan_once()
            self.monitor(setup_enabled=False).scan_once()
            self.monitor(stopping=True).scan_once()
            stopped = self.monitor(); stopped.stop(); stopped.scan_once()
            refresh.assert_not_called()
        self.assertIsNotNone(stale.problem)
        shared = self.monitor(setup_enabled=False); shared.start()
        self.assertIsNone(shared.thread)

    def test_workspace_switch_reads_only_new_active_workspace(self):
        first = self.register(auto_refresh=True)
        other = self.root / 'other-data'; core.initialize(other, 'Owner')
        second = projects.save_project(other, {'name': 'Same repo, separate workspace', 'path': str(self.repo), 'auto_refresh': True})['project']
        monitor = self.monitor(); monitor.server.data_path = other; monitor.scan_once()
        self.assertNotIn('last_refresh', self.current())
        self.assertIn('last_refresh', projects.list_projects(other)['projects'][0])
        self.assertNotIn((str(self.data), first['id']), monitor.checks)
        self.assertIn((str(other), second['id']), monitor.checks)

    def test_failure_isolated_and_recovers_next_scan(self):
        first = self.register(auto_refresh=True)
        config = core.load_config(self.data)
        config['projects'].insert(0, {**config['projects'][0], 'id': 'project-missing', 'name': 'Missing', 'path': str(self.root / 'missing')})
        core.save_config(self.data, config)
        monitor = self.monitor(); monitor.scan_once()
        self.assertEqual(monitor.checks[(str(self.data), 'project-missing')]['state'], 'error')
        self.assertEqual(monitor.checks[(str(self.data), first['id'])]['state'], 'captured')
        monitor.scan_once()
        self.assertEqual(monitor.checks[(str(self.data), first['id'])]['state'], 'up-to-date')

    def test_legacy_registration_remains_off(self):
        self.register()
        config = core.load_config(self.data); del config['projects'][0]['auto_refresh']; core.save_config(self.data, config)
        with patch.object(projects, '_git') as git:
            self.monitor().scan_once(); git.assert_not_called()
        self.assertNotIn('last_refresh', self.current())

    def test_running_service_captures_without_refresh_requests_and_stops(self):
        project = self.register()
        server = MnemosServer(('127.0.0.1', 0), self.data)
        server.project_monitor.interval = .04
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        def wait_for(predicate):
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if predicate(): return
                threading.Event().wait(.025)
            self.fail('Background capture did not complete')
        def toggle(value):
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=8)
            try:
                conn.request('POST', '/api/projects/automatic', json.dumps({**self.current(), 'auto_refresh': value}),
                             {'Content-Type': 'application/json', 'X-Mnemos-Workspace': server.workspace_id})
                response = conn.getresponse(); result = json.loads(response.read())
                self.assertEqual(response.status, 200, result)
            finally: conn.close()
        try:
            toggle(True)
            wait_for(lambda: 'last_refresh' in self.current())
            self.write('README.md', '# Nimbus\n\nAutomatically captured revision.'); commit = self.commit()
            wait_for(lambda: self.current()['last_refresh']['commit'] == commit)
            toggle(False)
            self.write('README.md', 'Do not capture when disabled'); self.commit()
            # Wait for actual poll passes, not just an arbitrary clock delay.
            with patch.object(server.project_monitor, 'scan_once', wraps=server.project_monitor.scan_once) as scan:
                wait_for(lambda: scan.call_count >= 2)
            self.assertEqual(self.current()['last_refresh']['commit'], commit)
        finally:
            server.shutdown(); server.server_close(); thread.join(2)
        server.project_monitor.thread.join(2)
        self.assertFalse(server.project_monitor.thread.is_alive())
        self.assertIs(self.current()['auto_refresh'], False)
