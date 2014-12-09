# Copyright 2014 OpenStack Foundation
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

import sqlalchemy.orm.exc as sa_exc

import neutron.db.api as db
from neutron.plugins.ml2.drivers.cisco.n1kv import exceptions as n1kv_exc
from neutron.plugins.ml2.drivers.cisco.n1kv import n1kv_models


def add_network_binding(network_id,
                        netp_id,
                        db_session=None):
    """
    Create the network to network profile binding.

    :param db_session: database session
    :param network_id: UUID representing the network
    :param netp_id: network profile ID based on which this network
                    is created
    """
    db_session = db_session or db.get_session()
    binding = n1kv_models.N1kvNetworkBinding(network_id=network_id,
                                             profile_id=netp_id)
    db_session.add(binding)
    db_session.flush()
    return binding


def get_network_profile_by_type(segment_type, db_session=None):
    """Retrieve a network profile using its type."""
    db_session = db_session or db.get_session()
    try:
        return (db_session.query(n1kv_models.NetworkProfile).
                filter_by(segment_type=segment_type).one())
    except sa_exc.NoResultFound:
        raise n1kv_exc.NetworkProfileNotFound(profile=segment_type)


def get_network_profile_by_name(name, db_session=None):
    """Retrieve a network profile using its name."""
    db_session = db_session or db.get_session()
    try:
        return (db_session.query(n1kv_models.NetworkProfile).
                filter_by(name=name).one())
    except sa_exc.NoResultFound:
        raise n1kv_exc.NetworkProfileNotFound(profile=name)


def get_network_profile_by_uuid(id, db_session=None):
    """Retrieve a network profile using its UUID."""
    db_session = db_session or db.get_session()
    try:
        return (db_session.query(n1kv_models.NetworkProfile).
                filter_by(id=id).one())
    except sa_exc.NoResultFound:
        raise n1kv_exc.NetworkProfileNotFound(profile=id)


def add_network_profile(netp_name, netp_type, db_session=None):
    """Create a network profile."""
    db_session = db_session or db.get_session()
    netp = n1kv_models.NetworkProfile(name=netp_name,
                                      segment_type=netp_type)
    db_session.add(netp)
    db_session.flush()
    return netp


def remove_network_profile(netp_id, db_session=None):
    """Delete a network profile."""
    db_session = db_session or db.get_session()
    nprofile = (db_session.query(n1kv_models.NetworkProfile).
                filter_by(id=netp_id).first())
    if nprofile:
        db_session.delete(nprofile)
        db_session.flush()


def get_policy_profile_by_name(name, db_session=None):
    """Retrieve policy profile by name."""
    db_session = db_session or db.get_session()
    try:
        return (db_session.query(n1kv_models.PolicyProfile).
                filter_by(name=name).one())
    except sa_exc.NoResultFound:
        raise n1kv_exc.PolicyProfileNotFound(profile=name)


def get_policy_profile_by_uuid(db_session, id):
    """Retrieve policy profile by its UUID."""
    try:
        return (db_session.query(n1kv_models.PolicyProfile).
                filter_by(id=id).one())
    except sa_exc.NoResultFound:
        raise n1kv_exc.PolicyProfileNotFound(profile=id)

def get_network_binding(network_id, db_session=None):
    """Retrieve network binding."""
    db_session = db_session or db.get_session()
    try:
        return (db_session.query(n1kv_models.N1kvNetworkBinding).
                filter_by(network_id=network_id).one())
    except sa_exc.NoResultFound:
        raise n1kv_exc.NetworkBindingNotFound(network_id=network_id)


def add_policy_binding(port_id, pprofile_id, db_session=None):
    """Create the port to policy profile binding."""
    db_session = db_session or db.get_session()
    binding = n1kv_models.N1kvPortBinding(port_id=port_id,
                                          profile_id=pprofile_id)
    db_session.add(binding)
    db_session.flush()
    return binding


def get_policy_binding(port_id, db_session=None):
    """Retrieve port to policy profile binding."""
    db_session = db_session or db.get_session()
    try:
        return (db_session.query(n1kv_models.N1kvPortBinding).
                filter_by(port_id=port_id).one())
    except sa_exc.NoResultFound:
        raise n1kv_exc.PortBindingNotFound(port_id=port_id)
