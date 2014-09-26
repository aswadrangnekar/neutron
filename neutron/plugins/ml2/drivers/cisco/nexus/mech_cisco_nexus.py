# Copyright 2013 OpenStack Foundation
# All rights reserved.
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

"""
ML2 Mechanism Driver for Cisco Nexus platforms.
"""

from oslo.config import cfg

from neutron.common import constants as n_const
from neutron.db import api as db_api
from neutron.extensions import portbindings
from neutron.openstack.common import log as logging
from neutron.plugins.common import constants as p_const
from neutron.plugins.ml2 import db as ml2_db
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2.drivers.cisco.nexus import config as conf
from neutron.plugins.ml2.drivers.cisco.nexus import constants as const
from neutron.plugins.ml2.drivers.cisco.nexus import exceptions as excep
from neutron.plugins.ml2.drivers.cisco.nexus import nexus_db_v2 as nxos_db
from neutron.plugins.ml2.drivers.cisco.nexus import nexus_network_driver

LOG = logging.getLogger(__name__)


class CiscoNexusMechanismDriver(api.MechanismDriver):

    """Cisco Nexus ML2 Mechanism Driver."""

    def initialize(self):
        # Create ML2 device dictionary from ml2_conf.ini entries.
        conf.ML2MechCiscoConfig()

        # Extract configuration parameters from the configuration file.
        self._nexus_switches = conf.ML2MechCiscoConfig.nexus_dict
        LOG.debug(_("nexus_switches found = %s"), self._nexus_switches)

        self.driver = nexus_network_driver.CiscoNexusDriver()

        # Required for VXLAN configured segments.
        # TODO(rcurran) - remove?
        self.vif_type = portbindings.VIF_TYPE_OVS
        self.vif_details = {portbindings.CAP_PORT_FILTER: True}

    def _valid_network_segment(self, segment):
        return (cfg.CONF.ml2_cisco.managed_physical_network is None or
                cfg.CONF.ml2_cisco.managed_physical_network ==
                segment[api.PHYSICAL_NETWORK])

    def _get_vlanid(self, segment):
        if (segment and segment[api.NETWORK_TYPE] == p_const.TYPE_VLAN and
            self._valid_network_segment(segment)):
            return segment.get(api.SEGMENTATION_ID)

    def _is_deviceowner_compute(self, port):
        return port['device_owner'].startswith('compute')

    def _is_status_active(self, port):
        return port['status'] == n_const.PORT_STATUS_ACTIVE

    def _get_switch_info(self, host_id):
        host_connections = []
        for switch_ip, attr in self._nexus_switches:
            if str(attr) == str(host_id):
                for port_id in (
                    self._nexus_switches[switch_ip, attr].split(',')):
                    if ':' in port_id:
                        intf_type, port = port_id.split(':')
                    else:
                        intf_type, port = 'ethernet', port_id
                    host_connections.append((switch_ip, intf_type, port))

        if host_connections:
            return host_connections
        else:
            raise excep.NexusComputeHostNotConfigured(host=host_id)

    def _configure_nve_db(self, vni, mcast_group, host_id):
        """Create the nexus NVE database entry.

        Called during update precommit port event.
        """
        host_connections = self._get_switch_info(host_id)
        for switch_ip, intf_type, nexus_port in host_connections:
            nxos_db.add_nexusnve_binding(vni, switch_ip, mcast_group)

    def _configure_nve_member(self, vni, mcast_group, host_id):
        """Add "member vni" configuration to the NVE interface.

        Called during update postcommit port event.
        """
        host_connections = self._get_switch_info(host_id)

        for switch_ip, intf_type, nexus_port in host_connections:
            # Check to see if this is the first binding to use this vni on this
            # switch. Configure switch accordingly.
            bindings = nxos_db.get_nve_switch_bindings(switch_ip)
            if len(bindings) == 1:
                LOG.debug(_("Nexus: create NVE interface"))
                loopback = self._nexus_switches.get(
                    (switch_ip, 'nve_src_intf'), '0')
                self.driver.enable_vxlan_feature(switch_ip, const.NVE_INT_NUM,
                                                 loopback)
            LOG.debug(_("Nexus: add member"))
            self.driver.create_nve_member(switch_ip, const.NVE_INT_NUM, vni,
                                          mcast_group)

    def _delete_nve_db(self, vni, mcast_group, host_id):
        """Delete the nexus NVE database entry.

        Called during delete precommit port event.
        """
        rows = nxos_db.get_nve_vni_bindings(vni)
        for row in rows:
            nxos_db.remove_nexusnve_binding(row.vni, row.switch_ip)

    def _delete_nve_member(self, vni, mcast_group, host_id):
        """Remove "member vni" configuration from the NVE interface.

        Called during delete postcommit port event.
        """
        host_connections = self._get_switch_info(host_id)
        for switch_ip, intf_type, nexus_port in host_connections:
            self.driver.delete_nve_member(switch_ip, const.NVE_INT_NUM, vni)

            if not nxos_db.get_nve_switch_bindings(switch_ip):
                self.driver.disable_vxlan_feature(switch_ip)

    def _configure_nxos_db(self, vlan_id, device_id, host_id, vni):
        """Create the nexus database entry.

        Called during update precommit port event.
        """
        host_connections = self._get_switch_info(host_id)
        for switch_ip, intf_type, nexus_port in host_connections:
            port_id = '%s:%s' % (intf_type, nexus_port)
            nxos_db.add_nexusport_binding(port_id, str(vlan_id), str(vni),
                                          switch_ip, device_id)

    def _configure_switch_entry(self, vlan_id, device_id, host_id, vni):
        """Create a nexus switch entry.

        if needed, create a VLAN in the appropriate switch/port and
        configure the appropriate interfaces for this VLAN.

        Called during update postcommit port event.
        """
        vlan_name = cfg.CONF.ml2_cisco.vlan_name_prefix + str(vlan_id)
        host_connections = self._get_switch_info(host_id)

        # (nexus_port,switch_ip) will be unique in each iteration.
        # But switch_ip will repeat if host has >1 connection to same switch.
        # So track which switch_ips already have vlan created in this loop.
        vlan_already_created = []
        for switch_ip, intf_type, nexus_port in host_connections:

            # The VLAN needs to be created on the switch if no other
            # instance has been placed in this VLAN on a different host
            # attached to this switch.  Search the existing bindings in the
            # database.  If all the instance_id in the database match the
            # current device_id, then create the VLAN, but only once per
            # switch_ip.  Otherwise, just trunk.
            all_bindings = nxos_db.get_nexusvlan_binding(vlan_id, switch_ip)
            previous_bindings = [row for row in all_bindings
                    if row.instance_id != device_id]
            if previous_bindings or (switch_ip in vlan_already_created):
                LOG.debug("Nexus: trunk vlan %s"), vlan_name
                self.driver.enable_vlan_on_trunk_int(switch_ip, vlan_id,
                                                     intf_type, nexus_port)
            else:
                vlan_already_created.append(switch_ip)
                LOG.debug("Nexus: create & trunk vlan %s"), vlan_name
                self.driver.create_and_trunk_vlan(
                    switch_ip, vlan_id, vlan_name, intf_type, nexus_port, vni)

    def _delete_nxos_db(self, vlan_id, device_id, host_id, vni):
        """Delete the nexus database entry.

        Called during delete precommit port event.
        """
        try:
            rows = nxos_db.get_nexusvm_bindings(vlan_id, device_id)
            for row in rows:
                nxos_db.remove_nexusport_binding(row.port_id, row.vlan_id,
                                    row.vni, row.switch_ip, row.instance_id)
        except excep.NexusPortBindingNotFound:
            return

    def _delete_switch_entry(self, vlan_id, device_id, host_id, vni):
        """Delete the nexus switch entry.

        By accessing the current db entries determine if switch
        configuration can be removed.

        Called during delete postcommit port event.
        """
        host_connections = self._get_switch_info(host_id)

        # (nexus_port,switch_ip) will be unique in each iteration.
        # But switch_ip will repeat if host has >1 connection to same switch.
        # So track which switch_ips already have vlan removed in this loop.
        vlan_already_removed = []
        for switch_ip, intf_type, nexus_port in host_connections:

            # if there are no remaining db entries using this vlan on this
            # nexus switch port then remove vlan from the switchport trunk.
            port_id = '%s:%s' % (intf_type, nexus_port)
            try:
                nxos_db.get_port_vlan_switch_binding(port_id, vlan_id,
                                                     switch_ip)
            except excep.NexusPortBindingNotFound:
                self.driver.disable_vlan_on_trunk_int(switch_ip, vlan_id,
                                                      intf_type, nexus_port)

                # if there are no remaining db entries using this vlan on this
                # nexus switch then remove the vlan.
                try:
                    nxos_db.get_nexusvlan_binding(vlan_id, switch_ip)
                except excep.NexusPortBindingNotFound:

                    # Do not perform a second time on same switch
                    if switch_ip not in vlan_already_removed:
                        self.driver.delete_vlan(switch_ip, vlan_id)
                        vlan_already_removed.append(switch_ip)

    def _is_segment_nexus_vxlan(self, segment):
        return segment[api.NETWORK_TYPE] == p_const.TYPE_NEXUS_VXLAN

    def _get_segments(self, top_segment, bottom_segment):
        # Return vlan segment and vxlan segment (if configured).
        if top_segment is None:
            return None, None
        elif self._is_segment_nexus_vxlan(top_segment):
            return bottom_segment, top_segment
        else:
            return top_segment, None

    def _is_vm_migration(self, context, vlan_segment, orig_vlan_segment):
        if not vlan_segment and orig_vlan_segment:
            return (context.current.get(portbindings.HOST_ID) !=
                    context.original.get(portbindings.HOST_ID))

    def _port_action_vlan(self, port, segment, func, vni):
        """Verify configuration and then process event."""
        device_id = port.get('device_id')
        host_id = port.get(portbindings.HOST_ID)
        vlan_id = self._get_vlanid(segment)

        if vlan_id and device_id and host_id:
            func(vlan_id, device_id, host_id, vni)
        else:
            fields = "vlan_id " if not vlan_id else ""
            fields += "device_id " if not device_id else ""
            fields += "host_id" if not host_id else ""
            raise excep.NexusMissingRequiredFields(fields=fields)

    def _port_action_vxlan(self, port, segment, func):
        """Verify configuration and then process event."""
        mcast_group = segment.get(api.PHYSICAL_NETWORK)
        host_id = port.get(portbindings.HOST_ID)
        vni = segment.get(api.SEGMENTATION_ID)

        if vni and mcast_group and host_id:
            func(vni, mcast_group, host_id)
            return vni
        else:
            fields = "vni " if not vni else ""
            fields += "mcast_group " if not mcast_group else ""
            fields += "host_id" if not host_id else ""
            raise excep.NexusMissingRequiredFields(fields=fields)

    def update_port_precommit(self, context):
        """Update port pre-database transaction commit event."""
        vlan_segment, vxlan_segment = self._get_segments(
                                        context.top_bound_segment,
                                        context.bottom_bound_segment)
        orig_vlan_segment, orig_vxlan_segment = self._get_segments(
                                        context.original_top_bound_segment,
                                        context.original_bottom_bound_segment)

        # if VM migration is occurring then remove previous database entry
        # else process update event.
        if self._is_vm_migration(context, vlan_segment, orig_vlan_segment):
            vni = self._port_action_vxlan(context.original, orig_vxlan_segment,
                        self._delete_nve_db) if orig_vxlan_segment else 0
            self._port_action_vlan(context.original, orig_vlan_segment,
                                   self._delete_nxos_db, vni)
        else:
            if (self._is_deviceowner_compute(context.current) and
                self._is_status_active(context.current)):
                vni = self._port_action_vxlan(context.current, vxlan_segment,
                            self._configure_nve_db) if vxlan_segment else 0
                self._port_action_vlan(context.current, vlan_segment,
                                       self._configure_nxos_db, vni)

    def update_port_postcommit(self, context):
        """Update port non-database commit event."""
        vlan_segment, vxlan_segment = self._get_segments(
                                        context.top_bound_segment,
                                        context.bottom_bound_segment)
        orig_vlan_segment, orig_vxlan_segment = self._get_segments(
                                        context.original_top_bound_segment,
                                        context.original_bottom_bound_segment)

        # if VM migration is occurring then remove previous nexus switch entry
        # else process update event.
        if self._is_vm_migration(context, vlan_segment, orig_vlan_segment):
            vni = self._port_action_vxlan(context.original, orig_vxlan_segment,
                        self._delete_nve_member) if orig_vxlan_segment else 0
            self._port_action_vlan(context.original, orig_vlan_segment,
                                   self._delete_switch_entry, vni)
        else:
            if (self._is_deviceowner_compute(context.current) and
                self._is_status_active(context.current)):
                vni = self._port_action_vxlan(context.current, vxlan_segment,
                            self._configure_nve_member) if vxlan_segment else 0
                self._port_action_vlan(context.current, vlan_segment,
                                       self._configure_switch_entry, vni)

    def delete_port_precommit(self, context):
        """Delete port pre-database commit event."""
        if self._is_deviceowner_compute(context.current):
            vlan_segment, vxlan_segment = self._get_segments(
                                                context.top_bound_segment,
                                                context.bottom_bound_segment)
            vni = self._port_action_vxlan(context.current, vxlan_segment,
                             self._delete_nve_db) if vxlan_segment else 0
            self._port_action_vlan(context.current, vlan_segment,
                                   self._delete_nxos_db, vni)

    def delete_port_postcommit(self, context):
        """Delete port non-database commit event."""
        if self._is_deviceowner_compute(context.current):
            vlan_segment, vxlan_segment = self._get_segments(
                                                context.top_bound_segment,
                                                context.bottom_bound_segment)
            vni = self._port_action_vxlan(context.current, vxlan_segment,
                             self._delete_nve_member) if vxlan_segment else 0
            self._port_action_vlan(context.current, vlan_segment,
                                   self._delete_switch_entry, vni)

    def bind_port(self, context):
        # TODO(rcurran): update this method
        LOG.debug(_("Attempting to bind port %(port)s on network %(network)s"),
                  {'port': context.current['id'],
                   'network': context.network.current['id']})
        for segment in context.segments_to_bind:
            if self._is_segment_nexus_vxlan(segment):
                # Bind the VXLAN static segment to this driver.
                # TODO(rcurran) - need correct vif_type, vif_details
                # since we're not using set_binding, how does vif type,
                # details and status get set for segment?
                """
                context.set_binding(segment[api.ID],
                                    self.vif_type,
                                    self.vif_details,
                                    status=n_const.PORT_STATUS_ACTIVE)
                """
                # Continue to create VLAN dynamic segment.

                # TODO(rcurran) - do we need to support multiple physnets
                # on different switches per hostname?
                host_id = context.current.get(portbindings.HOST_ID)
                host_connections = self._get_switch_info(host_id)
                physnets = []
                for switch_ip, attr2, attr3 in host_connections:
                    physnet = self._nexus_switches.get((switch_ip, 'physnet'))
                    if physnet:
                        physnets.append(physnet)

                if not physnets:
                    LOG.debug(_("No physical network(s) found for vlan "
                                "segment allocation(s)."))
                    return

                # Nexus overlay configured. Allocate vlan and configure switch
                # with VXLAN information.
                network_id = context.current['network_id']
                vlan_segment = {api.NETWORK_TYPE: 'vlan'}
                session = db_api.get_session()

                # TODO(rcurran) - do we support multiple physnets per hostname?
                for physnet in physnets:
                    vlan_segment[api.PHYSICAL_NETWORK] = physnet
                    context.allocate_dynamic_segment(vlan_segment)

                    # Retrieve the dynamically allocated segment.
                    # Database has provider_segment dictionary key.
                    dynamic_segment = ml2_db.get_dynamic_segment(session,
                                                    network_id, physnet)

                    # Have other drivers bind the VLAN dynamic segment.
                    if dynamic_segment:
                        context.continue_binding(segment[api.ID],
                                                 [dynamic_segment])
            else:
                LOG.debug(_("Refusing to bind port for segment ID %(id)s, "
                            "segment %(seg)s, phys net %(physnet)s, and "
                            "network type %(nettype)s"),
                          {'id': segment[api.ID],
                           'seg': segment[api.SEGMENTATION_ID],
                           'physnet': segment[api.PHYSICAL_NETWORK],
                           'nettype': segment[api.NETWORK_TYPE]})
