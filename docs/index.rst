=====================
ElectrumX for PEPEPOW
=====================

.. image:: https://api.cirrus-ci.com/github/spesmilo/electrumx.svg?branch=master
    :target: https://cirrus-ci.com/github/spesmilo/electrumx
.. image:: https://coveralls.io/repos/github/spesmilo/electrumx/badge.svg
    :target: https://coveralls.io/github/spesmilo/electrumx

This project is based on `kyuupichan/electrumx <https://github.com/kyuupichan/electrumx>`_
and maintained for PEPEPOW deployment and operations.

ElectrumX allows users to run their own Electrum server. It connects to a full
node and indexes the blockchain, allowing efficient querying of address history.

The current version is |release|.

Source Code
===========

The project is hosted on `GitHub
<https://github.com/spesmilo/electrumx/>`_.  and uses `Cirrus CI
<https://cirrus-ci.com/github/spesmilo/electrumx>`_ for Continuous
Integration.

Please submit an issue on the `bug tracker
<https://github.com/spesmilo/electrumx/issues>`_ if you have found a
bug or have a suggestion to improve the server.

License
=======

Python version at least 3.10 is required.

The code is released under the `MIT Licence
<https://github.com/spesmilo/electrumx/LICENCE>`_.

Getting Started
===============

See :ref:`HOWTO`.

For this repository, prioritize the PEPEPOW deployment runbook and runtime
configuration references below.

Documentation
=============

.. toctree::

   HOWTO
   pepepow_deployment
   environment
   protocol
   peer_discovery
   rpc-interface

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
