# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013, Nachi Ueno, NTT I3, Inc.
# All Rights Reserved.
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
import mock

from neutron.openstack.common import uuidutils
from neutron.plugins.common import constants
from neutron.services.vpn.device_drivers import (
    cisco_csr_rest_client as csr_client)
from neutron.services.vpn.device_drivers import cisco_ipsec as ipsec_driver
from neutron.tests import base

_uuid = uuidutils.generate_uuid
FAKE_HOST = 'fake_host'
FAKE_ROUTER_ID = _uuid()
FAKE_VPN_SERVICE = {
    'id': _uuid(),
    'router_id': FAKE_ROUTER_ID,
    'admin_state_up': True,
    'status': constants.PENDING_CREATE,
    'subnet': {'cidr': '10.0.0.0/24'},
    'ipsec_site_connections': [
        {'peer_cidrs': ['20.0.0.0/24',
                        '30.0.0.0/24']},
        {'peer_cidrs': ['40.0.0.0/24',
                        '50.0.0.0/24']}]
}
CSR_REST_CLIENT=('neutron.services.vpn.device_drivers.'
                 'cisco_csr_rest_client.CsrRestClient')

class TestIPsecDeviceDriver(base.BaseTestCase):
    def setUp(self, driver=ipsec_driver.CiscoCsrIPsecDriver):
        super(TestIPsecDeviceDriver, self).setUp()
        self.addCleanup(mock.patch.stopall)

# DELETE START
        for klass in [
            'os.makedirs',
            'os.path.isdir',
            'neutron.agent.linux.utils.replace_file',
            'neutron.openstack.common.rpc.create_connection',
            'neutron.services.vpn.device_drivers.ipsec.'
                'OpenSwanProcess._gen_config_content',
            'shutil.rmtree',
        ]:
            mock.patch(klass).start()
        self.execute = mock.patch(
            'neutron.agent.linux.utils.execute').start()
# DELETE END            
        self.agent = mock.Mock()
        self.driver = driver(
            self.agent,
            FAKE_HOST)
#         self.driver.agent_rpc = mock.Mock()

    def test_create_psk(self):
        conn_info = {'site_conn': {'id': 123,
                                   'psk': 'secret',
                                   'peer_address': '192.168.1.2'},
                     'cisco': {'site_conn_id': 'Tunnel0',
                               'ike_policy_id': 222,
                               'ipsec_policy_id': 333}
                     }
        with mock.patch(CSR_REST_CLIENT) as MockCsr:
            mock_csr = MockCsr.return_value
            context = mock.Mock()
            self.driver.create_ipsec_site_connection(context, conn_info)
            self.assertEqual(mock_csr.mock_calls, [call.create_pre_shared_key({u'keyring-name': 123, u'pre-shared-key-list': [{u'encrypted': False, u'key': 'secret', u'peer-address': '192.168.1.2'}]})])
            

#     def test_vpnservice_updated(self):
#         with mock.patch.object(self.driver, 'sync') as sync:
#             context = mock.Mock()
#             self.driver.vpnservice_updated(context)
#             sync.assert_called_once_with(context, [])

#     def test_create_router(self):
#         process_id = _uuid()
#         process = mock.Mock()
#         process.vpnservice = FAKE_VPN_SERVICE
#         self.driver.processes = {
#             process_id: process}
#         self.driver.create_router(process_id)
#         process.enable.assert_called_once_with()
#
#     def test_destroy_router(self):
#         process_id = _uuid()
#         process = mock.Mock()
#         process.vpnservice = FAKE_VPN_SERVICE
#         self.driver.processes = {
#             process_id: process}
#         self.driver.destroy_router(process_id)
#         process.disable.assert_called_once_with()
#         self.assertNotIn(process_id, self.driver.processes)
#
#     def test_sync_added(self):
#         self.driver.agent_rpc.get_vpn_services_on_host.return_value = [
#             FAKE_VPN_SERVICE]
#         context = mock.Mock()
#         process = mock.Mock()
#         process.vpnservice = FAKE_VPN_SERVICE
#         process.connection_status = {}
#         process.status = constants.ACTIVE
#         process.updated_pending_status = True
#         self.driver.process_status_cache = {}
#         self.driver.processes = {
#             FAKE_ROUTER_ID: process}
#         self.driver.sync(context, [])
#         self.agent.assert_has_calls([
#             mock.call.add_nat_rule(
#                 FAKE_ROUTER_ID,
#                 'POSTROUTING',
#                 '-s 10.0.0.0/24 -d 20.0.0.0/24 -m policy '
#                 '--dir out --pol ipsec -j ACCEPT ',
#                 top=True),
#             mock.call.add_nat_rule(
#                 FAKE_ROUTER_ID,
#                 'POSTROUTING',
#                 '-s 10.0.0.0/24 -d 30.0.0.0/24 -m policy '
#                 '--dir out --pol ipsec -j ACCEPT ',
#                 top=True),
#             mock.call.add_nat_rule(
#                 FAKE_ROUTER_ID,
#                 'POSTROUTING',
#                 '-s 10.0.0.0/24 -d 40.0.0.0/24 -m policy '
#                 '--dir out --pol ipsec -j ACCEPT ',
#                 top=True),
#             mock.call.add_nat_rule(
#                 FAKE_ROUTER_ID,
#                 'POSTROUTING',
#                 '-s 10.0.0.0/24 -d 50.0.0.0/24 -m policy '
#                 '--dir out --pol ipsec -j ACCEPT ',
#                 top=True),
#             mock.call.iptables_apply(FAKE_ROUTER_ID)
#         ])
#         process.update.assert_called_once_with()
#         self.driver.agent_rpc.update_status.assert_called_once_with(
#             context,
#             [{'status': 'ACTIVE',
#              'ipsec_site_connections': {},
#              'updated_pending_status': True,
#              'id': FAKE_VPN_SERVICE['id']}])
#
#     def test_sync_removed(self):
#         self.driver.agent_rpc.get_vpn_services_on_host.return_value = []
#         context = mock.Mock()
#         process_id = _uuid()
#         process = mock.Mock()
#         process.vpnservice = FAKE_VPN_SERVICE
#         self.driver.processes = {
#             process_id: process}
#         self.driver.sync(context, [])
#         process.disable.assert_called_once_with()
#         self.assertNotIn(process_id, self.driver.processes)
#
#     def test_sync_removed_router(self):
#         self.driver.agent_rpc.get_vpn_services_on_host.return_value = []
#         context = mock.Mock()
#         process_id = _uuid()
#         self.driver.sync(context, [{'id': process_id}])
#         self.assertNotIn(process_id, self.driver.processes)
