# coding=gbk
"""
 * User: ������
 * Date: 2018/5/21
 * Time: 11:25
 * Description: ����ģ��
"""
import sys 
sys.path.append("..\src")
from src.remote import Remote

def CheckErr(err, result):
    if(err):
        print('err:',err)
    elif result:
        print('res:', result)

remote = Remote({'server': 'ws://ts5.jingtum.com:5020', 'local_sign':True})
def test(err, result):
	if (err):
		return print('err:',err)
	tx = remote.buildPaymentTx({
		account: 'jB7rxgh43ncbTX4WeMoeadiGMfmfqY2xLZ',
		to: 'jDUjqoDZLhzx4DCf6pvSivjkjgtRESY62c',
		amount: {
		"value": 0.5,
		"currency": "SWT",
		"issuer": ""
		}
	})
	tx.setSecret('sn37nYrQ6KPJvTFmaBYokS3FjXUWd')
	tx.addMemo('��jDUjqoDZLhzx4DCf6pvSivjkjgtRESY62c֧��0.5swt.')#��ѡ
	tx.submit(CheckErr)

remote.connect(test)