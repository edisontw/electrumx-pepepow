# Copyright (c) 2026, the ElectrumX authors
#
# All rights reserved.

'''Deserializer for PEPEPOW transactions.'''

from electrumx.lib.tx import Deserializer


class DeserializerPepepow(Deserializer):
    '''PEPEPOW currently uses standard transaction serialization.'''

