import unittest

from lbryum import commands, wallet, transaction, bip32
from lbryum.lbrycrd import claim_id_hash, encode_claim_id_hex, rev_hex
from lbryum.constants import TYPE_ADDRESS, TYPE_CLAIM, TYPE_UPDATE, TYPE_SUPPORT, TYPE_SCRIPT
from lbryum.errors import NotEnoughFunds


PUBKEY = 'xpub661MyMwAqRbcF8M4CH68NvHEc6TUNaVhXwmGrsagNjrCja49H9L4ziJGe8YmaSBPbY4ZmQPQeW5CK6fiwx2EH6VxQab3zwDzZVWVApDSVNh'


class MocStore(dict):
    def put(self, key, val):
        self[key] = val


class MocWallet(wallet.NewWallet):

    def __init__(self):
        super(MocWallet, self).__init__(MocStore())
        self.accounts = {'0': bip32.BIP32_Account({'xpub': PUBKEY})}
        self.send_tx_connected = True
        self.send_tx_success = True
        self.sent_transactions = []

    def send_tx(self, tx, timeout=300):
        self.sent_transactions.append(tx)
        if not self.send_tx_connected:
            raise Exception("Not connected.")
        tx.raw = tx.serialize()
        return self.send_tx_success, tx.raw

    def sign_transaction(self, tx, password):
        for txi in tx._inputs:
            if 'signatures' not in txi:
                txi.update({
                    'signatures': [None],
                    'pubkeys': ['02e61d176da16edd1d258a200ad9759ef63adf8e14cd97f53227bae35cdb84d2f6'],
                    'x_pubkeys': ['02e61d176da16edd1d258a200ad9759ef63adf8e14cd97f53227bae35cdb84d2f6']
                })

    def add_address_transaction(self, amount):
        in_address = self.create_new_address()
        out_address = self.create_new_address()
        tx = transaction.Transaction.from_io(
            [{
                'address': in_address,
                'prevout_hash': '3140eb24b43386f35ba69e3875eb6c93130ac66201d01c58f598defc949a5c2a',
                'prevout_n': 0
            }],
            [
                (TYPE_ADDRESS, out_address, amount)
            ]
        )
        self.sign_transaction(tx, '')
        tx.raw = tx.serialize()
        tx_hash = tx.hash()
        self.history.setdefault(out_address, [])
        self.history[out_address].append([tx.hash(), 1])
        self.txo[tx_hash] = {
            out_address: [(0, amount, False)]
        }
        self.transactions[tx_hash] = tx
        return out_address

    def add_claim_transaction(self, name, amount):
        in_address = self.create_new_address()
        out_address = self.create_new_address()
        tx = transaction.Transaction.from_io(
            [{
                'address': in_address,
                'prevout_hash': '3140eb24b43386f35ba69e3875eb6c93130ac66201d01c58f598defc949a5c2a',
                'prevout_n': 0
            }],
            [
                (TYPE_CLAIM | TYPE_SCRIPT, ((name, ''), out_address), amount)
            ]
        )
        self.sign_transaction(tx, '')
        tx.raw = tx.serialize()
        tx_hash = tx.hash()
        self.history.setdefault(out_address, [])
        self.history[out_address].append([tx.hash(), 1])
        self.txo[tx_hash] = {
            out_address: [(0, amount, False)]
        }
        self.transactions[tx_hash] = tx
        return tx_hash


class MocNetwork(object):
    pass


class MocCommands(commands.Commands):
    def __init__(self, config=None, wallet=None, network=None):
        self.config = config or {}
        self.wallet = wallet or MocWallet()
        self.network = network or MocNetwork()
        self._password = ''


class TestClaimCommand(unittest.TestCase):

    def test_claim_success(self):
        cmds = MocCommands()
        cmds.wallet.add_address_transaction(110000000)
        out = cmds.claim('test', 'value', 1, skip_validate_schema=True, raw=True)
        self.assertEqual(True, out['success'])

    def test_claim_not_enough_funds(self):
        cmds = MocCommands()
        out = cmds.claim('test', '[payload]', 1, skip_validate_schema=True, raw=True)
        self.assertEqual(False, out['success'])
        self.assertEqual('Not enough funds', out['reason'])

    def test_update_success(self):
        cmds = MocCommands()
        cmds.wallet.add_address_transaction(510000000)
        cmds.wallet.add_claim_transaction('test', 1)
        out = cmds.update('test', '[payload]', amount=1, tx_fee=1, skip_validate_schema=True, raw=True)
        self.assertEqual(True, out['success'])

    def test_update_not_enough_funds(self):
        cmds = MocCommands()
        cmds.wallet.add_address_transaction(110000000)
        cmds.wallet.add_claim_transaction('test', 1)
        out = cmds.update('test', '[payload]', amount=1, tx_fee=1, skip_validate_schema=True, raw=True)
        self.assertEqual(False, out['success'])
        self.assertEqual('Not enough funds', out['reason'])

    def test_update_not_found(self):
        cmds = MocCommands()
        cmds.wallet.add_address_transaction(510000000)
        cmds.wallet.add_claim_transaction('test', 1)
        out = cmds.update('foo', '[payload]', amount=1, tx_fee=1, skip_validate_schema=True, raw=True)
        self.assertEqual(False, out['success'])
        self.assertEqual('No claim to update', out['reason'])

    def test_support_success(self):
        cmds = MocCommands()
        cmds.wallet.add_address_transaction(510000000)
        tx = cmds.wallet.add_claim_transaction('test', 1)
        claim_id = encode_claim_id_hex(claim_id_hash(rev_hex(tx).decode('hex'), 0))
        out = cmds.support('test', claim_id, 1, tx_fee=1)
        self.assertEqual(True, out['success'])

    def test_support_invalid_claim_id(self):
        cmds = MocCommands()
        cmds.wallet.add_address_transaction(10000000)
        out = cmds.support('test', 'deadbeef', 1, tx_fee=1)
        self.assertEqual(False, out['success'])
        self.assertEqual('Invalid claim id', out['reason'])

    def test_support_not_enough_funds(self):
        cmds = MocCommands()
        cmds.wallet.add_address_transaction(10000000)
        tx = cmds.wallet.add_claim_transaction('test', 1)
        claim_id = encode_claim_id_hex(claim_id_hash(rev_hex(tx).decode('hex'), 0))
        out = cmds.support('test', claim_id, 1, tx_fee=1)
        self.assertEqual(False, out['success'])
        self.assertEqual('Not enough funds', out['reason'])


class TestAbandonCommand(unittest.TestCase):

    def test_abandon_success(self):
        cmds = MocCommands()
        cmds.wallet.add_address_transaction(510000000)
        tx = cmds.wallet.add_claim_transaction('test', 1)
        claim_id = encode_claim_id_hex(claim_id_hash(rev_hex(tx).decode('hex'), 0))
        out = cmds.abandon(claim_id=claim_id)
        self.assertEqual(True, out['success'])

    def test_abandoning_claim_with_fee_greater_than_claim_value(self):
        cmds = MocCommands()
        cmds.wallet.add_address_transaction(9500)
        tx = cmds.wallet.add_claim_transaction('test', 1000)
        claim_id = encode_claim_id_hex(claim_id_hash(rev_hex(tx).decode('hex'), 0))
        cmds.abandon(claim_id=claim_id)
        sent = cmds.wallet.sent_transactions[0]
        self.assertEqual(len(sent._inputs), 2)
        self.assertEqual(sent._inputs[0]['value'], 1000)
        self.assertEqual(sent._inputs[1]['value'], 9500)
        self.assertEqual(len(sent._outputs), 1)
        self.assertEqual(sent._outputs[0][2], 900)


class FormatTests(unittest.TestCase):

    def test_format_lbrycrd_keys(self):
        a = {'amount': 100000000}
        out = commands.format_amount_value(a)
        self.assertEqual(1.0, out['amount'])
