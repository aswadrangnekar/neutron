# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 Red Hat, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import contextlib

import eventlet
import eventlet.timeout
import fixtures

from neutron.agent.linux import async_process
from neutron.tests import base


class TestAsyncProcess(base.BaseTestCase):

    def setUp(self):
        super(TestAsyncProcess, self).setUp()
        self.test_file_path = self.useFixture(
            fixtures.TempDir()).join("test_async_process.tmp")
        self.data = [str(x) for x in xrange(4)]
        with file(self.test_file_path, 'w') as f:
            f.writelines('%s\n' % item for item in self.data)

    def _check_stdout(self, proc):
        # Ensure that all the output from the file is read
        output = []
        while output != self.data:
            new_output = list(proc.iter_stdout())
            if new_output:
                output += new_output
            eventlet.sleep(0.01)

    @contextlib.contextmanager
    def assert_max_execution_time(self, max_execution_time=5):
        with eventlet.timeout.Timeout(max_execution_time, False):
            yield
            return
        self.fail('Execution of this test timed out')

    def test_stopping_async_process_lifecycle(self):
        with self.assert_max_execution_time():
            proc = async_process.AsyncProcess(['tail', '-f',
                                               self.test_file_path])
            proc.start()
            self._check_stdout(proc)
            proc.stop()

            # Ensure that the process and greenthreads have stopped
            proc._process.wait()
            self.assertEqual(proc._process.returncode, -9)
            for watcher in proc._watchers:
                watcher.wait()

    def test_async_process_respawns(self):
        with self.assert_max_execution_time():
            proc = async_process.AsyncProcess(['tail', '-f',
                                               self.test_file_path],
                                              respawn_interval=0)
            proc.start()

            # Ensure that the same output is read twice
            self._check_stdout(proc)
            pid = proc._get_pid_to_kill()
            proc._kill_process(pid)
            self._check_stdout(proc)
            proc.stop()
