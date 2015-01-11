__author__ = 'hareesh'

import logging

from neutron.plugins.cisco.cfg_agent.device_drivers.asr1k import (
    asr1k_routing_driver as asr_driver)
from neutron.plugins.cisco.cfg_agent.service_helpers.routing_svc_helper \
    import RouterInfo

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    device_params = {'management_ip_address': '10.86.7.178',
                     'protocol_port': 22,
                     'timeout': 30,
                     "credentials": {
                         'username': "stack",
                         'password': 'cisco'
                     }}
    router = {'id': 'dummy',
              'name': 'router1'}
    ri = RouterInfo("dummy", router)
    port = {'ip_cidr': '10.0.2.1/24',
            'hosting_info': {
                'hosting_mac': 'fa:16:3e:b3:0e:48',
                'hosting_port_id': 'dummy_id',
                'hosting_port_name': u't2_p:1',
                'segmentation_id': 101,
                'physical_interface': 'GigabitEthernet0/0/0'}
            }
    driver = asr_driver.ASR1kRoutingDriver(**device_params)
    if driver._get_connection():
        logging.info('Connection Established!')
        driver.router_added(ri)
        driver.internal_network_added(ri,port)
        driver.internal_network_removed(ri, port)
        driver.router_removed(ri)