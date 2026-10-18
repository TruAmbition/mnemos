"""Opt-in project polling attached to the lifetime of the local portal."""
from contextlib import nullcontext
import threading

from . import core, projects

INTERVAL_SECONDS = 60


class ProjectMonitor:
    def __init__(self, server, interval=INTERVAL_SECONDS):
        self.server = server
        self.interval = interval
        self.stopped = threading.Event()
        self.wake = threading.Event()
        self.thread = None
        self.checks = {}
        self.problem = None

    def start(self):
        if not self.server.setup_enabled or self.thread is not None:
            return
        self.thread = threading.Thread(target=self._run, name='mnemos-project-refresh', daemon=True)
        self.thread.start()

    def stop(self):
        self.stopped.set()
        self.wake.set()

    def _run(self):
        while not self.stopped.is_set():
            self.wake.clear()
            self.scan_once()
            self.wake.wait(self.interval)

    def scan_once(self):
        server = self.server
        try:
            with server.workspace_lock:
                if self.stopped.is_set() or server.stopping or not server.setup_enabled:
                    return
                server.assert_selection_current()
                data = server.data_path
                if not (data / 'config.json').exists():
                    return
                identifiers = [p['id'] for p in projects._entries(data) if p.get('auto_refresh') is True]
                self.problem = None
            for identifier in identifiers:
                with server.workspace_lock:
                    if self.stopped.is_set() or server.stopping or server.data_path != data:
                        return
                    # Use the same pointer->data lock order as browser mutations.
                    with core.storage_lock(server.installation_file.parent) if server.installation_file else nullcontext():
                        server.assert_selection_current()
                        try:
                            result = projects.refresh_if_changed(data, identifier)
                            self.checks[(str(data), identifier)] = {**result, 'checked_at': core.now()}
                        except Exception as error:
                            # Never log repository output, credentials, or tracebacks.
                            detail = str(error) if isinstance(error, core.MnemosError) else 'Automatic refresh could not complete. Check the checkout and file permissions.'
                            self.checks[(str(data), identifier)] = {'state': 'error', 'checked_at': core.now(), 'detail': detail}
        except Exception:
            # Invalid config or a changed installation pointer must fail closed.
            with server.workspace_lock:
                self.problem = 'Automatic refresh is paused. Reload the active workspace or restart Mnemos, and check its configuration.'

    def overview(self, result):
        for project in result['projects']:
            project['automatic_status'] = (self.checks.get((str(self.server.data_path), project['id']), {'state': 'waiting'})
                                           if project.get('auto_refresh') is True else {'state': 'off'})
        result['automatic_refresh'] = {'interval_seconds': self.interval,
            'running': bool(self.thread and self.thread.is_alive() and not self.stopped.is_set()),
            'problem': self.problem,
            'scope': 'Checks local committed HEAD while the local Mnemos service runs. No remote fetching or login-time startup.'}
        return result
