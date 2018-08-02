# coding=gbk
"""
 * User: ������
 * Date: 2018/5/21
 * Time: 11:25
 * Description: ����ģ��
"""
import unittest
from numbers import Number

#from src.logger import logger
from src.remote import Remote

class OfferTest(unittest.TestCase):
    def test_build_offer_create(self):
        remote = Remote(local_sign=True)
        options = {
            'type': 'Sell',
            'account': 'jB7rxgh43ncbTX4WeMoeadiGMfmfqY2xLZ',
            'taker_gets': {
                'value': '0.01',
                'currency': '8100000036000020160622201606300120000002',
                'issuer': 'jBciDE8Q3uJjf111VeiUNM775AMKHEbBLS'
            },
            'taker_pays': {
                'value': '1',
                'currency': 'SWT',
                'issuer': ''
            }
        }

        if not isinstance(remote.connect(None), Exception):
            tx = remote.build_offer_create_tx(options)
            tx.set_secret('sn37nYrQ6KPJvTFmaBYokS3FjXUWd')
            s=tx.submit()
            result=remote.parse_payment(s)
            print('test_build_offer_create result is', result)

    def test_build_offer_cancel(self):
        remote = Remote(local_sign=True)
        options = {
            'sequence': 1777,
            'account': 'jB7rxgh43ncbTX4WeMoeadiGMfmfqY2xLZ',
        }

        if not isinstance(remote.connect(None), Exception):
            tx = remote.build_offer_cancel_tx(options)
            tx.set_secret('sn37nYrQ6KPJvTFmaBYokS3FjXUWd')
            s=tx.submit()
            result=remote.parse_payment(s)
            print('test_build_offer_cancel result is', result)


if __name__ == '__main__':
    unittest.main()
