from electrumx.lib.coins import Coin, Pepepow


def test_pepepow_lookup_coin_class():
    assert Coin.lookup_coin_class('PEPEPOW', 'mainnet') is Pepepow


def test_pepepow_constants():
    assert Pepepow.RPC_PORT == 8833
    assert Pepepow.GENESIS_HASH == '00000a308cc3b469703a3bc1aa55bc251a71c9287d7b413242592c0ab0a31f13'
