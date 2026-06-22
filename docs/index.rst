=====================
ElectrumX for PEPEPOW
=====================

This project is based on `kyuupichan/electrumx <https://github.com/kyuupichan/electrumx>`_
and maintained for PEPEPOW deployment and operations.

ElectrumX allows users to run their own Electrum server. It connects to a full
node and indexes the blockchain, allowing efficient querying of address history.

The current version is |release|.

Source Code
===========

The PEPEPOW-maintained repository is hosted on GitHub:

* `edisontw/electrumx-pepepow <https://github.com/edisontw/electrumx-pepepow>`_

This fork focuses on PEPEPOW mainnet integration, deployment examples,
operations documentation, and PEPEPOW-specific smoke checks.

License
=======

Python version at least 3.10 is required.

The code is released under the MIT Licence.

Getting Started
===============

For PEPEPOW operators, start with these guides:

* :ref:`pepepow_deployment` for initial setup and systemd deployment.
* :ref:`pepepow_operations` for maintenance, monitoring, troubleshooting, and
  application usage.

Documentation
=============

.. toctree::

   HOWTO
   pepepow_deployment
   pepepow_operations
   environment
   protocol
   peer_discovery
   rpc-interface

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
