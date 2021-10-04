"""Helpers."""
import logging
import os
from pathlib import Path
import json
import socket
import sysconfig
import sys

from .errors import NotReady, LoginFailed
from .credential import Credentials, DEFAULT_DEVICE_NAME
from .ddp import search, DDP_PORT, DEFAULT_UDP_PORT
from .ps5 import Ps5Legacy

_LOGGER = logging.getLogger(__name__)

DEFAULT_PATH = Path.home() / ".psremoteplay"
DEFAULT_PS5_FILE = DEFAULT_PATH / ".ps5_info.json"
DEFAULT_CREDS_FILE = DEFAULT_PATH / ".ps5_creds.json"
DEFAULT_GAMES_FILE = DEFAULT_PATH / ".ps5_games.json"

FILE_TYPES = {
    'ps5': str(DEFAULT_PS5_FILE),
    'credentials': str(DEFAULT_CREDS_FILE),
    'games': str(DEFAULT_GAMES_FILE),
}


# noqa: pylint: disable=no-self-use
class Helper:
    """Helpers for PS5. Used as class."""

    def __init__(self):
        """Init Class."""

    def has_devices(self, host=None, port=DEFAULT_UDP_PORT) -> list:
        """Return list of device status dicts that are discovered."""
        _LOGGER.debug("Searching for PS5 Devices")
        devices = search(host, port)
        for device in devices:
            _LOGGER.debug("Found PS5 at: %s", device['host-ip'])
        return devices

    def link(
            self,
            host: str,
            creds: str,
            pin: str,
            device_name=None,
            port=DEFAULT_UDP_PORT) -> tuple:
        """Return tuple. Perform pairing with PS5.

        :param host: Host IP Address of PS5 console
        :param creds: PSN Credential
        :param pin: 8 digit PIN displayed on PS5 when adding mobile device
        """

        if device_name is None:
            device_name = DEFAULT_DEVICE_NAME
        ps5 = Ps5Legacy(host, creds, device_name=device_name, port=port)
        is_ready = True
        is_login = True
        if not pin.isdigit():
            _LOGGER.error("Pin must be all numbers")
            is_login = False
        else:
            try:
                ps5.login(pin)
            except NotReady:
                is_ready = False
            except LoginFailed:
                is_login = False
            ps5.close()
        return is_ready, is_login

    def get_creds(self, device_name=None):
        """Return Credentials.

        :param device_name: Name to display in 2nd Screen App
        """

        if device_name is None:
            device_name = DEFAULT_DEVICE_NAME

        credentials = Credentials(device_name)
        return credentials.listen()

    def save_creds(self):
        """Save Creds to file."""
        creds = self.get_creds()
        if creds is not None:
            data = {'credentials': creds}
            self.save_files(DEFAULT_CREDS_FILE, data)
            return True
        return False

    def port_bind(self, ports: list) -> int:
        """Return port that are not able to bind.

        Returns first port that fails.
        :param ports: Ports to test
        """
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(1)
                sock.bind(('0.0.0.0', port))
                sock.close()
            except socket.error:
                sock.close()

                if port == DDP_PORT:
                    error_str = "Error binding to port."
                    path_str = ''
                    if sys.platform == 'linux':
                        py_path = self.get_exec_path()
                        path_str = (
                            " Try setcap command >"
                            "setcap 'cap_net_bind_service=+ep' {}"
                        ).format(py_path)
                    _LOGGER.error('%s%s', error_str, path_str)

                return int(port)
            return None

    def check_data(self, file_type=None, file_name=None) -> bool:
        """Return True if data is present in file.

        :param file_type: Type of file
        :param file_name: Name of file
        """
        if file_name is None:
            file_name = self.check_files(file_type)
        with open(file_name, "r") as _r_file:
            data = json.load(_r_file)
            _r_file.close()
        if data:
            return True
        return False

    def check_files(self, file_type: str) -> str:
        """Create file if it does not exist. Return full path.

        :param file_type: Type of file
        """
        file_path = str(DEFAULT_PATH)
        if not os.path.exists(file_path):
            os.mkdir(file_path)
        if file_type in FILE_TYPES:
            file_name = FILE_TYPES[file_type]
            if not os.path.isfile(file_name):
                with open(file_name, "w+") as _file_name:
                    json.dump(fp=_file_name, obj={})
                    _file_name.close()
            return file_name
        return None

    def load_files(self, file_type: str) -> dict:
        """Load data as JSON. Return data.

        :param file_type: Type of file
        """
        file_name = self.check_files(file_type)
        with open(file_name, "r") as _r_file:
            data = json.load(_r_file)
            _r_file.close()
        return data

    def save_files(self, data: dict, file_type=None) -> str:
        """Save file with data dict. Return file path.

        :param data: Data to save
        :param file_type: Type of file
        """
        if not isinstance(data, dict) or not data:
            return None
        if file_type in FILE_TYPES:
            file_name = FILE_TYPES[file_type]
        else:
            return None

        _data = data
        with open(file_name, "w+") as _w_file:
            json.dump(fp=_w_file, obj=_data)
            _w_file.close()
        return file_name

    # noqa: pylint: disable=no-member
    def get_exec_path(self) -> str:
        """Return correct exec path for setcap util."""
        try:
            config = sysconfig.get_config_vars()
            base = config['projectbase']
            version = config['py_version_short']
            py_str = '/python'
            py_path = '{}{}{}'.format(
                base,
                py_str,
                version,
            )
            if not Path(py_path).is_symlink():
                return py_path
        except (KeyError, AttributeError):
            _LOGGER.debug("Error retrieving exec path")
        return sys.executable
