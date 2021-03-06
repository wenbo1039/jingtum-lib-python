# coding=gbk
"""
 * User: ������
 * Date: 2018/7/21
 * Time: 11:25
 * Description: ����ģ��
"""
import unittest

from jingtum_python_lib.remote import Remote
from jingtum_python_lib.logger import logger


class RequestTest(unittest.TestCase):
    @staticmethod
    def test_select_ledger():
        remote = Remote()
        if not isinstance(remote.connect(), Exception):
            req = remote.request_account_info({'account': 'j9fE48ebcvwnKSGnPdtN6jGNM9yVBMVaH8'})
            req.select_ledger(838796)
            result = req.submit()
            logger.info(result)

    @staticmethod
    def test_submit():
        remote = Remote()
        if not isinstance(remote.connect(), Exception):
            req = remote.request_account_info({'account': 'j9fE48ebcvwnKSGnPdtN6jGNM9yVBMVaH8'})
            result = req.submit()
            logger.info(result)

if __name__ == '__main__':
    unittest.main()
