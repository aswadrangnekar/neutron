# Copyright 2014 Cisco Systems, Inc.  All rights reserved.
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
#
# @author: Bob Melander, Cisco Systems, Inc.

from neutron.plugins.cisco.device_manager.hosting_device_drivers import (
    HostingDeviceDriver)


class TestHostingDeviceDriver(HostingDeviceDriver):

    def hosting_device_name(self):
        return "Test_HD"

    def create_configdrive_files(self, context, mgmtport):
        return {}

    def delete_configdrive_files(self, context, mgmtport):
        pass
