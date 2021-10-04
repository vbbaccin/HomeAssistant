PyPSRemotePlay
==========================================

|BuildStatus| |PypiVersion| |PyPiPythonVersions| |CodeCov|

|Docs|

Description
--------------------
A full Python implementation based on the Node.js package, ps4-waker, which is an unofficial API for the PS Remote Play App.

This module is mainly targeted towards developers although the module does include a basic CLI.


**Disclaimer**:
This project/module and I are not affiliated with or endorsed by Sony Interactive Entertainment LLC. As such this project may break at any time.

Features
---------
This module can perform almost every feature found in the PS Remote Play App.

- PS4 power and playing media state/status reporting
- Remote control
- Power on and standby control
- Starting a specific game/media
- Media information retrieval from the Playstation Store

Compatibility
--------------------
Tested on:

- Environment: Python 3.6/3.7/3.8

- Operating System: Debian


Installation
--------------------
Package can be installed with pip or from source.

It is advised to install the module in a virtual env.

Create virtual env first:

.. code:: bash

    python -m venv .
    source bin/activate

To install from pip:

.. code:: bash

    pip install psremoteplay

To install from source clone this repository and run from top-level:

.. code:: bash

    pip install -r requirements.txt
    python setup.py install

Protocol
--------------------
UDP is used to get status updates and retrieve user credentials. TCP is used to send commands to the PS4 Console.

Ports
--------------------
This module uses UDP port 1987 by default as the source port for polling the PS4.

PS4 listens on ports 987 (Priveleged) to fetch user PSN credentials.

In order to obtain user credentials, the Python Interpreter needs access to port 987 on the host system.
The credential service pretends to be a PS4 console and will receive broadcast packets from the PS Remote Play app on port 987.

Example:

.. code:: bash

    sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3.9
    
This is so you do not need sudo/root priveleges to run.


Cover Art Issues
--------------------
If you find that media art cannot be found. Please post an issue with your Region, Country, Title of game, an ID of game.

Known Issues
--------------------
- PS Command inconsistent.
- On-Screen Keyboard is not implemented.


Credits
--------------------
Thanks to hthiery for writing the underlying socket protocol in Python. https://www.home-assistant.io/components/ps4/ and https://github.com/ktnrg45/pyps4-2ndscreen


References
--------------------

- https://github.com/home-assistant/core/tree/dev/homeassistant/components/ps4
- https://www.home-assistant.io/components/ps4/
- https://github.com/ktnrg45/pyps4-2ndscreen


