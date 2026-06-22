=====================
ElectrumX for PEPEPOW
=====================

This project is based on `kyuupichan/electrumx <https://github.com/kyuupichan/electrumx>`_
and maintained for PEPEPOW deployment and operations.

ElectrumX allows users to run their own Electrum server. This PEPEPOW fork
connects to a PEPEPOW full node, indexes the blockchain, and provides Electrum
protocol access for wallets and applications.

The current version is |release|.

Source Code
===========

The PEPEPOW-maintained repository is hosted on GitHub:

* `edisontw/electrumx-pepepow <https://github.com/edisontw/electrumx-pepepow>`_

This fork focuses on PEPEPOW mainnet integration, deployment examples,
operations documentation, and PEPEPOW-specific smoke checks.

Core Guides
===========

For PEPEPOW operators, these are the only required docs:

* :ref:`pepepow_deployment` for initial setup and systemd deployment.
* :ref:`pepepow_operations` for maintenance, monitoring, troubleshooting, and
  application usage.

Documentation
=============

.. toctree::
   :maxdepth: 2

   pepepow_deployment
   pepepow_operations

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
