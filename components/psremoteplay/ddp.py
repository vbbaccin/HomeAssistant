# -*- coding: utf-8 -*-
"""Device Discovery Protocol for PS5."""
from __future__ import print_function

import asyncio
import logging
import re
import select
import socket
import time
from typing import Optional

_LOGGER = logging.getLogger(__name__)

BROADCAST_IP = '255.255.255.255'
UDP_IP = '0.0.0.0'
UDP_PORT = 0
DEFAULT_UDP_PORT = 1987
DDP_PORT = 987
DDP_VERSION = '00020020'
DDP_TYPE_SEARCH = 'SRCH'
DDP_TYPE_LAUNCH = 'LAUNCH'
DDP_TYPE_WAKEUP = 'WAKEUP'
DDP_MSG_TYPES = (DDP_TYPE_SEARCH, DDP_TYPE_LAUNCH, DDP_TYPE_WAKEUP)
DEFAULT_POLL_COUNT = 5
DEFAULT_STANDBY_DELAY = 50
STATUS_OK = 200
STATUS_STANDBY = 620

class DDPProtocol(asyncio.DatagramProtocol):
    """Async UDP Client."""

    def __init__(self, max_polls=DEFAULT_POLL_COUNT):
        """Init Instance."""
        super().__init__()
        self.callbacks = {}
        self.max_polls = max_polls
        self._transport = None
        self._remote_port = DDP_PORT
        self._local_port = UDP_PORT
        self._message = get_ddp_search_message()
        self._standby_start = 0

    def __repr__(self):
        return (
            "<{}.{} local_port={} max_polls={}>".format(
                self.__module__,
                self.__class__.__name__,
                self.local_port,
                self.max_polls,
            )
        )

    def _set_write_port(self, port):
        """Only used for tests."""
        self._remote_port = port

    def set_max_polls(self, poll_count: int):
        """Set number of unreturned polls neeeded to assume no status."""
        self.max_polls = poll_count

    def connection_made(self, transport):
        """On Connection."""
        self._transport = transport
        sock = self._transport.get_extra_info('socket')
        self._local_port = sock.getsockname()[1]
        _LOGGER.debug("PS5 Transport created with port: %s", self.local_port)

    def send_msg(self, ps5, message=None):
        """Send Message."""
        # PS5 won't respond to polls right after standby
        if self.polls_disabled:
            elapsed = time.time() - self._standby_start
            seconds = DEFAULT_STANDBY_DELAY - elapsed
            _LOGGER.debug("Polls disabled for %s seconds", round(seconds, 2))
            return
        self._standby_start = 0
        if message is None:
            message = self._message
        sock = self._transport.get_extra_info('socket')
        _LOGGER.debug(
            "SENT MSG @ DDP Proto SPORT=%s DEST=%s",
            sock.getsockname()[1], (ps5.host, self._remote_port))
        self._transport.sendto(
            message.encode('utf-8'),
            (ps5.host, self._remote_port))

        # Track polls that were never returned.
        ps5.poll_count += 1

        # Assume PS5 is not available.
        if ps5.poll_count > self.max_polls:
            if not ps5.unreachable:
                _LOGGER.info("PS5 @ %s is unreachable", ps5.host)
                ps5.unreachable = True
            ps5.status = None
            if ps5.host in self.callbacks:
                callback = self.callbacks[ps5.host].get(ps5)
                if callback is not None:
                    callback()

    def datagram_received(self, data, addr):
        """When data is received."""
        if data is not None:
            sock = self._transport.get_extra_info('socket')
            _LOGGER.debug(
                "RECV MSG @ DDP Proto DPORT=%s SRC=%s",
                sock.getsockname()[1], addr)
            self._handle(data, addr)

    def _handle(self, data, addr):
        data = parse_ddp_response(data.decode('utf-8'))
        data[u'host-ip'] = addr[0]

        address = addr[0]

        if address in self.callbacks:
            for ps5, callback in self.callbacks[address].items():
                ps5.poll_count = 0
                ps5.unreachable = False
                old_status = ps5.status
                ps5.status = data
                if old_status != data:
                    _LOGGER.debug("Status: %s", ps5.status)
                    callback()
                    # Status changed from OK to Standby/Turned Off
                    if old_status is not None and \
                            old_status.get('status_code') == STATUS_OK and \
                            ps5.status.get('status_code') == STATUS_STANDBY:
                        self._standby_start = time.time()
                        _LOGGER.debug(
                            "Status changed from OK to Standby."
                            "Disabling polls for %s seconds",
                            DEFAULT_STANDBY_DELAY)

    def connection_lost(self, exc):
        """On Connection Lost."""
        if self._transport is not None:
            _LOGGER.error("DDP Transport Closed")
            self._transport.close()

    def error_received(self, exc):
        """Handle Exceptions."""
        _LOGGER.warning("Error received at DDP Transport")

    def close(self):
        """Close Transport."""
        self._transport.close()
        self._transport = None
        _LOGGER.debug(
            "Closing DDP Transport: Port=%s",
            self._local_port)

    def add_callback(self, ps5, callback):
        """Add callback to list. One per PS5 Object."""
        if ps5.host not in self.callbacks:
            self.callbacks[ps5.host] = {}
        self.callbacks[ps5.host][ps5] = callback

    def remove_callback(self, ps5, callback):
        """Remove callback from list."""
        if ps5.host in self.callbacks:
            if self.callbacks[ps5.host][ps5] == callback:
                self.callbacks[ps5.host].pop(ps5)

                # If no callbacks remove host key also.
                if not self.callbacks[ps5.host]:
                    self.callbacks.pop(ps5.host)

    @property
    def local_port(self):
        """Return local port."""
        return self._local_port

    @property
    def remote_port(self):
        """Return remote port."""
        return self._remote_port

    @property
    def polls_disabled(self):
        """Return true if polls disabled."""
        elapsed = time.time() - self._standby_start
        if elapsed < DEFAULT_STANDBY_DELAY:
            return True
        self._standby_start = 0
        return False


async def async_create_ddp_endpoint(sock=None, port=DEFAULT_UDP_PORT):
    """Create Async UDP endpoint."""
    loop = asyncio.get_event_loop()
    if sock is None:
        sock = get_socket(port=port)
    sock.settimeout(0)
    connect = loop.create_datagram_endpoint(
        lambda: DDPProtocol(),  # noqa: pylint: disable=unnecessary-lambda
        sock=sock,
    )
    transport, protocol = await loop.create_task(connect)
    return transport, protocol


def get_ddp_message(msg_type, data=None):
    """Get DDP message."""
    if msg_type not in DDP_MSG_TYPES:
        raise TypeError(
            "DDP MSG type: '{}' is not a valid type".format(msg_type))
    msg = u'{} * HTTP/1.1\n'.format(msg_type)
    if data is not None:
        for key, value in data.items():
            msg += '{}:{}\n'.format(key, value)
    msg += 'device-discovery-protocol-version:{}\n'.format(DDP_VERSION)
    return msg


def parse_ddp_response(rsp):
    """Parse the response."""
    data = {}
    if DDP_TYPE_SEARCH in rsp:
        _LOGGER.info("Received %s message", DDP_TYPE_SEARCH)
        return data
    app_name = None
    for line in rsp.splitlines():
        if 'running-app-name' in line:
            app_name = line
            app_name = app_name.replace('running-app-name:', '')
        re_status = re.compile(r'HTTP/1.1 (?P<code>\d+) (?P<status>.*)')
        line = line.strip()
        # skip empty lines
        if not line:
            continue
        if re_status.match(line):
            data[u'status_code'] = int(re_status.match(line).group('code'))
            data[u'status'] = re_status.match(line).group('status')
        else:
            values = line.split(':')
            data[values[0]] = values[1]
    if app_name is not None:
        data['running-app-name'] = app_name
    return data


def get_ddp_search_message():
    """Get DDP search message."""
    return get_ddp_message(DDP_TYPE_SEARCH)


def get_ddp_wake_message(credential):
    """Get DDP wake message."""
    data = {
        'user-credential': credential,
        'client-type': 'a',
        'auth-type': 'C',
    }
    return get_ddp_message(DDP_TYPE_WAKEUP, data)


def get_ddp_launch_message(credential):
    """Get DDP launch message."""
    data = {
        'user-credential': credential,
        'client-type': 'a',
        'auth-type': 'C',
    }
    return get_ddp_message(DDP_TYPE_LAUNCH, data)


def get_socket(port: Optional[int] = DEFAULT_UDP_PORT):
    """Return DDP socket object."""
    retries = 0
    sock = None
    while retries <= 1:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0)
        try:
            if hasattr(socket, "SO_REUSEPORT"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # noqa: pylint: disable=no-member
            sock.bind((UDP_IP, port))
        except socket.error as error:
            _LOGGER.error(
                "Error getting DDP socket with port: %s: %s", port, error)
            sock = None
            retries += 1
            port = UDP_PORT
        else:
            return sock
    return sock


def _send_recv_msg(
        host,
        msg,
        receive=True,
        send=True,
        sock=None,
        close=True):
    """Send a ddp message and receive the response."""
    response = None
    if sock is None:
        if not close:
            raise ValueError("Unspecified sockets must be closed")
        sock = get_socket()

    if send:
        if host == BROADCAST_IP:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            _LOGGER.debug("Broadcast enabled")

        sock.sendto(msg.encode('utf-8'), (host, DDP_PORT))
        _LOGGER.debug(
            "SENT DDP MSG: SPORT=%s DEST=%s",
            sock.getsockname()[1], (host, DDP_PORT))

    if receive:
        available, _, _ = select.select([sock], [], [], 0.01)
        if sock in available:
            response = sock.recvfrom(1024)
            _LOGGER.debug(
                "RECV DDP MSG: DPORT=%s SRC=%s",
                sock.getsockname()[1], response[1])
    if close:
        sock.close()
    return response


def _send_msg(host, msg, sock=None, close=True):
    """Send a ddp message."""
    return _send_recv_msg(
        host,
        msg,
        receive=False,
        send=True,
        sock=sock,
        close=close,
    )


def _recv_msg(host, msg, sock=None, close=True):
    """Send a ddp message."""
    return _send_recv_msg(
        host,
        msg,
        receive=True,
        send=False,
        sock=sock,
        close=close,
    )


def send_search_msg(host, sock=None):
    """Send SRCH message only."""
    msg = get_ddp_search_message()
    return _send_msg(host, msg, sock=sock)


def search(host=BROADCAST_IP, port=UDP_PORT, sock=None, timeout=3) -> list:
    """Return list of discovered PS5s."""
    ps_list = []
    msg = get_ddp_search_message()
    start = time.time()

    if host is None:
        host = BROADCAST_IP
    if sock is None:
        sock = get_socket(port=port)
    _LOGGER.debug("Sending search message")
    _send_msg(host, msg, sock=sock, close=False)
    while time.time() - start < timeout:
        data = addr = None
        response = _recv_msg(host, msg, sock=sock, close=False)
        if response is not None:
            data, addr = response
        if data is not None and addr is not None:
            data = parse_ddp_response(data.decode('utf-8'))
            if data not in ps_list and data:
                data[u'host-ip'] = addr[0]
                ps_list.append(data)
            if host != BROADCAST_IP:
                break
    sock.close()
    return ps_list


def get_status(host, port=UDP_PORT, sock=None):
    """Return status dict."""
    ps_list = search(host=host, port=port, sock=sock)
    if not ps_list:
        return None
    return ps_list[0]


def wakeup(host, credential, sock=None):
    """Wakeup PS5."""
    msg = get_ddp_wake_message(credential)
    _send_msg(host, msg, sock)


def launch(host, credential, sock=None):
    """Launch."""
    msg = get_ddp_launch_message(credential)
    _send_msg(host, msg, sock)
