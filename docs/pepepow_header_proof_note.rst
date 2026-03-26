======================================
PEPEPOW Header Proof Operational Note
======================================

This note records the current operational decision around header merkle proofs
on PEPEPOW.

Why this is acceptable
======================

* Upstream Electrum client code does not use ``cp_height`` in normal header
  requests. It requests:

  * ``blockchain.block.header`` as ``[height]``
  * ``blockchain.block.headers`` as ``[start_height, count]``

* In live verification, normal startup and idle serving behaved correctly
  without any ``cp_height > 0`` traffic.
* On PEPEPOW, the first ``cp_height > 0`` proof request is operationally too
  expensive because it still needs a one-time full header merkle cache
  initialization.

Operational conclusions
=======================

* Startup precache is too expensive on PEPEPOW and should remain disabled for
  normal operation.
* With precache disabled, idle CPU returns to sane levels.
* The repeat-work bug is fixed: repeated proof requests now join a shared lazy
  initialization task instead of starting repeated full-chain rehashes.
* The boolean parsing bug is fixed: ``false``, ``0``, ``no``, ``off``, and an
  empty value now correctly disable boolean environment flags such as
  ``PRECACHE_HEADER_MERKLE`` under systemd.

Deferred work
=============

Full ``cp_height`` proof optimization is deferred until there is real client
demand for it.

If future PEPEPOW clients actually require header proofs in normal operation,
the next design should avoid recomputing full-chain header hashes on demand.
The smallest safe direction is to persist header hashes incrementally and build
proofs from stored hashes rather than re-hashing raw headers across the chain.
