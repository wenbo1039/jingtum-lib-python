"""
 * Created with PyCharm.
 * User: 彭诗杰
 * Date: 2018/5/3
 * Time: 11:25
 * Description: main handler for backend system
 * one remote object one server, not many options onfiguration Parameters:
 * {
 *   local_sign: false, // default sign tx in jingtumd
 * }
"""
import json
from numbers import Number

from eventemitter import EventEmitter

from jingtum_python_baselib.wallet import Wallet
from src import util
from src.config import Config
from src.request import Request
from src.server import Server, WebSocketServer
from src.transaction import RelationTypes,AccountSetTypes,set_clear_flags,OfferTypes
from src.transaction import Transaction
from src.utils.cache import LRUCache
from src.utils.utils import utils

LEDGER_OPTIONS = ['closed', 'header', 'current']

"""
* ---------------------- transaction request --------------------
**
 * return string if swt amount
 * @param amount
 * @returns {Amount}
"""


def ToAmount(amount):
    if (amount.__contains__('value') and int(float(amount['value'])) > 100000000000):
        return Exception('invalid amount: amount\'s maximum value is 100000000000')
    if (amount['currency'] == Config.currency):
        # return new String(parseInt(Number(amount.value) * 1000000.00))
        return str(int(float(amount['value']) * 1000000))
    return amount

class Remote:
    def __init__(self, local_sign=False):
        # self.opts = options
        # if 'local_sign' in options:
        #     self.local_sign = options['local_sign']
        # self.url = options['server']
        self.local_sign = local_sign
        self.server = WebSocketServer(self)
        self.status = {"ledger_index": 0}
        self.requests = {}
        self.cache = LRUCache(100)  # 100 size，为cache和path设置缓存
        self.path = LRUCache(2100)  # 2100 size
        self.emitter = EventEmitter()

    def connect(self, callback):
        """
        connect first on every case
        :param callback:(error, result)
        :return:
        """
        if not self.server:
            return 'server not ready'
        self.server.connect(callback)

    def is_connected(self):
        """
        check is remote is connected to jingtumd
        :return:
        """
        return self.server.connected

    def handle_message(self, data):
        # 此处可能要处理异常情况
        data = json.loads(data)

        if not data:
            return
        if data.type == 'ledgerClosed':
            self.handle_ledger_closed(data)
        elif data.type == 'serverStatus':
            self.handle_server_status(data)
        elif data.type == 'response':
            self.handle_response(data)
        elif data.type == 'transaction':
            self.handle_transaction(data)
        elif data.type == 'path_find':
            self.handle_path_find(data)

    def handle_ledger_closed(self, data):
        """
        update server ledger status
        supply data to outside include ledger, reserve and fee
        :param data:
        :return:
        """
        if data.ledger_index > self.status.ledger_index:
            self.status.ledger_index = data.ledger_index
            self.status.ledger_time = data.ledger_time
            self.status.reserve_base = data.reserve_base
            self.status.reserve_inc = data.reserve_inc
            self.status.fee_base = data.fee_base
            self.status.fee_ref = data.fee_ref
            self.emitter.emit('ledger_closed', data)

    def handle_server_status(self, data):
        """
        supply data to outside about server status
        :param data:
        :return:
        """
        self.update_server_status(data)
        self.emitter.emit('server_status', data)

    def update_server_status(self, data):
        self.status.load_base = data.load_base
        self.status.load_factor = data.load_factor
        if data.pubkey_node:
            self.status.pubkey_node = data.pubkey_node

        self.status.server_status = data.server_status
        online = ~Server.online_states.indexOf(data.server_status)
        self.server.set_state('online' if online else 'offline')

    def handle_response(self, data):
        """
        handle response by every websocket request
        :param data:
        :return:
        """
        req_id = data.id
        if isinstance(req_id, Number) or req_id < 0 or req_id > self.requests.__len__():
            return
        request = self.requests[req_id]
        # pass process it when null callback
        del self.requests[req_id]
        del data.id

        # check if data contain server info
        if data.result and data.status == 'success' and data.result.server_status:
            self.update_server_status(data.result)

        # return to callback
        if data.status == 'success':
            result = request.filter(data.result)
            request.callback(None, result)
        elif data.status == 'error':
            request.callback(data.error_message or data.error_exception)

    def handle_transaction(self, data):
        """
        handle transaction type response
        TODO supply more friendly transaction data
        :param data:
        :return:
        """
        tx = data.transaction.hash
        if self.cache.get(tx):
            return
        self.cache.set(tx, 1)
        self.emitter.emit('transactions', data)

    def handle_path_find(self, data):
        """
        emit path find date to other
        :param data:
        :return:
        """
        self.emitter.emit('path_find', data)

    def submit(self, command, data):
        """
        request to server and backend
        :param command:
        :param data:
        :param filter:
        :return: {'req_id': req_id, 'callback': callback}
        """
        result = self.server.send_message(command, data)
        self.requests[result['req_id']] = {
            'command': command,
            'data': data,
            # 'filter': filter,
            'callback': result['callback']
        }
        return result
        #return result['callback']

    def subscribe(self, streams):
        request = Request(self, "subscribe", None)
        if streams:
            request.message['streams'] = streams if isinstance(streams, list) else [streams]
        return request

    # ---------------------- info request - -------------------
    # ---------------------- info request - -------------------
    # ---------------------- info request - -------------------

    def request_server_info(self):
        """
        请求服务器底层信息
        request server info
        return version, ledger, state and node id
        no option is required
        :return: {Request}
        """
        return Request(self, 'server_info', None)

    def request_ledger_closed(self):
        """
        获取最新账本信息
        request last closed ledger index and hash
        :return:   {Request}
        """
        return Request(self, 'ledger_closed', None)

    def request_ledger(self, options):
        """
        获取某一账本具体信息
        :param options: dict{ledger_index: Number, ledger_hash: hash, string}
        :return:
        """
        cmd = 'ledger'
        filter = True
        req = Request(self, cmd, filter)
        if not isinstance(options, dict):
            req.message['type'] = Exception('invalid options type')
            return req
        if options['ledger_index'] and isinstance(options['ledger_index'], int):
            req.message['ledger_index'] = options['ledger_index']
        elif options['ledger_hash'] and util.is_valid_hash(options['ledger_hash']):
            req.message['ledger_hash'] = options['ledger_hash']
        if 'full' in options.keys() and isinstance(options['full'], bool):
            req.message['full'] = options['full']
            filter = False
        if 'expand' in options.keys() and isinstance(options['expand'], bool):
            req.message['expand'] = options['expand']
            filter = False
        if 'transactions' in options.keys() and isinstance(options['transactions'], bool):
            req.message['transactions'] = options['transactions']
            filter = False
        if 'accounts' in options.keys() and isinstance(options['accounts'], bool):
            req.message['accounts'] = options['accounts']
            filter = False
        return req

    def request_tx(self, options):
        """
        查询某一交易具体信息
        :param options:
        :return:
        """
        req = Request(self, 'tx', None)
        if not isinstance(options, dict):
            req.message['type'] = Exception('invalid options type')
            return req
        if not util.is_valid_hash(options['hash']):
            req.message['hash'] = Exception('invalid tx hash')
            return req
        req.message['transaction'] = options['hash']
        return req

    def get_relation_type(self, type):
        if type == 'trustline':
            return 0
        elif type == 'authorize':
            return 1
        elif type == 'freeze':
            return 2

    def request_account(self, type, options, req):
        """
        :param type:
        :param options:
        :param req:
        :return:
        """
        req.command = type
        ledger = None
        peer = None
        limit = None
        marker = None
        account = options['account']
        if 'ledger' in options:
            ledger = options['ledger']
        if 'peer' in options:
            peer = options['peer']
        if 'limit' in options:
            limit = options['limit']
        if 'marker' in options:
            marker = options['marker']
        if 'type' in options:
            req.message['relation_type'] = self.get_relation_type(options['type'])
        if account:
            req.message['account'] = account
        if ledger:
            req.select_ledger(ledger)
        if util.is_valid_address(peer):
            req.message['peer'] = peer
        if limit:
            limit = int(limit)
            if limit < 0:
                limit = 0
            if limit > 1e9:
                limit = 1e9
            req.message['limit'] = limit
        if marker:
            req.message['marker'] = marker
        return req

    def request_account_info(self, options):
        """
        请求账号信息
        :param options: {account:’xxx’}
        :return:
        """
        req = Request(self, None, None)
        if not isinstance(options, dict):
            req.message['type'] = Exception('invalid options type')
            return req

        return self.request_account('account_info', options, req)

    def request_account_tums(self, options):
        """
        account tums    请求账号能交易代币
        return account supports currency, including
        send currency and receive currency
        :param options: account(required): the query account
        :return:
        """
        req = Request(self, None, None)
        if not isinstance(options, dict):
            req.message['type'] = Exception('invalid options type')
            return req

        return self.request_account('account_currencies', options, req)

    # import RelationTypes  src.transaction

    def request_account_relations(self, options):
        req = Request(self, None, None)
        if not isinstance(options, dict):
            req.message['type'] = Exception('invalid options type')
        if not ~RelationTypes.index(options['type']):
            req.message['relation_type'] = Exception('invalid realtion type')
            return req

        if options['type'] == 'trust':
            return self.request_account('account_lines', options, req)
        elif options['type'] == 'authorize':
            return
        elif options['type'] == 'freeze':
            return self.request_account('account_relation', options, req)

        req.message['msg'] = Exception('relation should not go here')
        return req

    def request_account_offers(self, options):
        """
        查询账户挂单
        :param options: account(required): the query account
        :return:
        """
        req = Request(self, None, None)
        if not isinstance(options, dict):
            req.message['type'] = Exception('invalid options type')
            return req

        return self.request_account('account_offers', options, req)

    def parse_payment(self, data):
        if isinstance(data, dict) and data['callback']:
            data = json.loads(data['callback'])
            if data['status']=='success':
                return {
                    'engine_result': data['result']['engine_result'],
                    'engine_result_code': data['result']['engine_result_code'],
                    'engine_result_message': data['result']['engine_result_message'],
                    'tx_blob': data['result']['tx_blob'],
                    'tx_json': data['result']['tx_json']
                }
            else:
                return data
        else:
            return data

    def parse_transaction(self, data):
        data = json.loads(data)
        return data['result']

    def parse_ledger(self, data):
        data = json.loads(data)
        return data['result']['ledger']

    def parse_ledger_closed(self, data):
        data = json.loads(data)
        return {
            'ledger_hash': data['result']['ledger_hash'],
            'ledger_index': data['result']['ledger_index']
        }

    def parse_server_info(self, data):
        data = json.loads(data)
        return {
            'version': data['result']['info']['build_version'],
            'ledgers': data['result']['info']['complete_ledgers'],
            'node': data['result']['info']['pubkey_node'],
            'state': data['result']['info']['server_state']
        }

    def parse_AccountTx_info(self, data):
        if isinstance(data, dict) and data['callback']:
            data = json.loads(data['callback'])
            if data['status'] == 'success':
                return {
                    'account': data['result']['account'],
                    'ledger_index_max': data['result']['ledger_index_max'],
                    'ledger_index_min': data['result']['ledger_index_min']
                }
            else:
                return {
                    'error': data['error']
                }
        else:
            return data
    def parse_OrderBook_info(self, data):
        if isinstance(data, dict) and data['callback']:
            data = json.loads(data['callback'])
            if data['status'] == 'success':
                return {
                    'ledger_current_index': data['result']['ledger_current_index'],
                    'offers': data['result']['offers']
                }
            else:
                return {
                    'error': data['error']
                }
        else:
            return data

    def parse_account_info(self, data):
        if isinstance(data, dict) and data['callback']:
            data = json.loads(data['callback'])
            return {
                'error': data['error'],
                'msg': data['error_message']
            }
        data = json.loads(data)
        account_data = {
            'account_data': data['result']['account_data'],
            'ledger_index': data['result']['ledger_current_index']
        }
        return account_data

    def parse_account_tums(self, data):
        data = json.loads(data)
        return {
            'ledger_index': data['result']['ledger_current_index'],
            'receive_currencies': data['result']['receive_currencies'],
            'send_currencies': data['result']['send_currencies'],
            'validated': data['result']['validated']
        }

    def parse_request_account_relations(self, data):
        data = json.loads(data)
        return {
            'account': data['result']['account'],
            'ledger_index': data['result']['ledger_current_index'],
            'lines': data['result']['lines'],
            'validated': data['result']['validated']
        }

    # def parse_request_account_offers(self, data):
    #     data = json.loads(data)
    #     print(data)
    #
    #     result = {
    #         'account': data['result']['account'],
    #         'ledger_index': data['result']['ledger_current_index'],
    #         'offers': data['result']['offers'],
    #         'seq': data['seq']
    #     }
    #     if data['result']['offers']:
    #
    #     return result

    """
     * payment
     * @param options
     *    source|from|account source account, required
     *    destination|to destination account, required
     *    amount payment amount, required
     * @returns {transaction}
     * 创建支付对象
    """

    def buildPaymentTx(self, options):
        tx = Transaction(self, None)
        if not options:  # typeof options没有转换
            tx.tx_json['obj'] = Exception('invalid options type')
            return tx
        if options.__contains__('source'):
            src = options['source']
        elif options.__contains__('from'):
            src = options['from']
        elif options.__contains__('account'):
            src = options['account']

        if options.__contains__('destination'):
            dst = options['destination']
        elif options.__contains__('to'):
            dst = options['to']
        amount = options['amount']

        if not Wallet.isValidAddress(src):
            tx.tx_json['src'] = Exception('invalid source address')
            return tx
        if not Wallet.isValidAddress(dst):
            tx.tx_json['dst'] = Exception('invalid destination address')
            return tx

        if not utils.isValidAmount(amount):
            tx.tx_json['amount'] = Exception('invalid amount')
            return tx

        tx.tx_json['TransactionType'] = 'Payment'
        tx.tx_json['Account'] = src
        tx.tx_json['Amount'] = ToAmount(amount)
        tx.tx_json['Destination'] = dst
        return tx

    ##设置账号属性
    def buildAccountSetTx(self, options):
        tx = Transaction(self, None)
        if not options:
            tx.tx_json['obj'] = ValueError('invalid options type')
            return tx
        if not options['type'] in AccountSetTypes:
            tx.tx_json['type'] = ValueError('invalid account set type')
            return tx
        if options['type'] == 'property':
            return self.__buildAccountSet(options, tx)
        elif options['type'] == 'delegate':
            return self.__buildDelegateKeySet(options, tx)
        elif options['type'] == 'signer':
            return self.__buildSignerSet() #not implement yet
        tx.tx_json['msg'] = Warning('build account set should not go here')
        return tx

    def __buildAccountSet(self, options, tx):
        if options.__contains__('source'):
            src = options['source']
        elif options.__contains__('from'):
            src = options['from']
        elif options.__contains__('account'):
            src = options['account']
        if options.__contains__('set_flag'):
            set_flag = options['set_flag']
        elif options.__contains__('set'):
            set_flag = options['set']
        if options.__contains__('clear_flag'):
            clear_flag = options['clear_flag']
        elif options.__contains__('clear'):
            clear_flag = options['clear']
        else:
            clear_flag = None
        if not Wallet.isValidAddress(src):
            tx.tx_json['src'] = Exception('invalid source address')
            return tx;

        tx.tx_json['TransactionType'] = 'AccountSet'
        tx.tx_json['Account'] = src

        SetClearFlags = set_clear_flags['AccountSet']

        if set_flag:
            set_flag = self.__prepareFlag(set_flag, SetClearFlags)
            if set_flag:
                tx.tx_json['SetFlag'] = set_flag

        if clear_flag is not None:
            clear_flag = self.__prepareFlag(clear_flag, SetClearFlags)
            if clear_flag:
                tx.tx_json['ClearFlag'] = clear_flag

        return tx

    def __prepareFlag(self, flag, SetClearFlags):
        result = None
        if isinstance(flag, (int,float)):
            result = flag
        else:
            if flag in SetClearFlags:
                result = SetClearFlags[flag]
            else:
                key = 'asf' + flag
                if key in SetClearFlags:
                    result = SetClearFlags[key]
        return result

    def __buildDelegateKeySet(self, options, tx):
        if options.__contains__('source'):
            src = options['source']
        elif options.__contains__('from'):
            src = options['from']
        elif options.__contains__('account'):
            src = options['account']
        delegate_key = options['delegate_key']

        if not Wallet.isValidAddress(src):
            tx.tx_json['delegate_key'] = Exception('invalid source address')
            return tx
        if not Wallet.isValidAddress(delegate_key):
            tx.tx_json['delegate_key'] = Exception('invalid regular key address')
            return tx
        tx.tx_json['TransactionType'] = 'SetRegularKey'
        tx.tx_json['Account'] = src
        tx.tx_json['RegularKey'] = delegate_key
        return tx

    def __buildSignerSet(self):
        return None

    # 挂单
    def buildOfferCreateTx(self, options):
        tx = Transaction(self, None)
        if not options:
            tx.tx_json['obj'] = TypeError('invalid options type')
            return tx

        offer_type = options['type']
        if options.__contains__('source'):
            src = options['source']
        elif options.__contains__('from'):
            src = options['from']
        elif options.__contains__('account'):
            src = options['account']

        if options.__contains__('taker_gets'):
            taker_gets = options['taker_gets']
        elif options.__contains__('pays'):
            taker_gets = options['pays']

        if options.__contains__('taker_pays'):
            taker_pays = options['taker_pays']
        elif options.__contains__('gets'):
            taker_pays = options['gets']

        if not Wallet.isValidAddress(src):
            tx.tx_json['src'] = Exception('invalid source address')
            return tx
        if not isinstance(offer_type, str) or not offer_type in OfferTypes:
            tx.tx_json['offer_type'] = TypeError('invalid offer type')
            return tx

        if isinstance(taker_gets, str) and not int(taker_gets) and not float(taker_gets):
            tx.tx_json['taker_gets2'] = Exception('invalid to pays amount')
            return tx
        if not taker_gets and not utils.isValidAmount(taker_gets):
            tx.tx_json['taker_gets2'] = Exception('invalid to pays amount object')
            return tx
        if isinstance(taker_pays, str) and not int(taker_pays) and not not float(taker_pays):
            tx.tx_json['taker_pays2'] = Exception('invalid to gets amount')
            return tx
        if not taker_pays and not utils.isValidAmount(taker_pays):
            tx.tx_json['taker_pays2'] = Exception('invalid to gets amount object')
            return tx

        tx.tx_json['TransactionType'] = 'OfferCreate'
        if offer_type is 'Sell':
            tx.setFlags(offer_type)
        tx.tx_json['Account'] = src
        tx.tx_json['TakerPays'] = ToAmount(taker_pays)
        tx.tx_json['TakerGets'] = ToAmount(taker_gets)
        return tx

    # 取消挂单
    def buildOfferCancelTx(self, options):
        tx = Transaction(self, None)
        if not options:
            tx.tx_json.obj = Exception('invalid options type')
            return tx
        if options.__contains__('source'):
            src = options['source']
        elif options.__contains__('from'):
            src = options['from']
        elif options.__contains__('account'):
            src = options['account']
        sequence = options['sequence']
        if not Wallet.isValidAddress(src):
            tx.tx_json['src'] = Exception('invalid source address')
            return tx
        if not int(sequence) and not float(sequence):
            tx.tx_json['sequence'] = Exception('invalid sequence param')
            return tx
        tx.tx_json['TransactionType'] = 'OfferCancel'
        tx.tx_json['Account'] = src
        tx.tx_json['OfferSequence'] = int(sequence)
        return tx

    def __buildRelationSet(self, options, tx):
        if options.__contains__('source'):
            src = options['source']
        elif options.__contains__('from'):
            src = options['from']
        elif options.__contains__('account'):
            src = options['account']

        des = options['target']
        limit = options['limit']

        if not Wallet.isValidAddress(src):
            tx.tx_json['src'] = Exception('invalid source address')
            return tx
        if not Wallet.isValidAddress(des):
            tx.tx_json['des'] = Exception('invalid target address')
            return tx
        if not utils.isValidAmount(limit):
            tx.tx_json['limit'] = Exception('invalid amount')
            return tx

        if options['type'] == 'unfreeze':
            tx.tx_json['TransactionType'] = 'RelationDel'
        else:
            tx.tx_json['TransactionType'] = 'RelationSet'
        tx.tx_json['Account'] = src
        tx.tx_json['Target'] = des
        if options['type'] == 'authorize':
            tx.tx_json['RelationType'] = '1'
        else:
            tx.tx_json['RelationType'] = '3'
        if limit:
            tx.tx_json['LimitAmount'] = limit
        return tx

    def __buildTrustSet(self, options, tx):
        if options.__contains__('source'):
            src = options['source']
        elif options.__contains__('from'):
            src = options['from']
        elif options.__contains__('account'):
            src = options['account']
        limit = options['limit']
        if options.__contains__('quality_out'):
            tx.tx_json['QualityIn'] = options['quality_out']
        if options.__contains__('quality_in'):
            tx.tx_json['QualityOut'] = options['quality_in']

        if not Wallet.isValidAddress(src):
            tx.tx_json['src'] = Exception('invalid source address')
            return tx
        if not utils.isValidAmount(limit):
            tx.tx_json['limit'] = Exception('invalid amount')
            return tx

        tx.tx_json['TransactionType'] = 'TrustSet'
        tx.tx_json['Account'] = src
        if limit:
            tx.tx_json['LimitAmount'] = limit
        return tx

    """
     * add wallet relation set
     * @param options
     *    type: Transaction.RelationTypes
     *    source|from|account source account, required
     *    limit limt amount, required
     *    quality_out, optional
     *    quality_in, optional
     * @returns {Transaction}
     * 创建关系对象
    """
    def buildRelationTx(self, options):
        tx = Transaction(self, None)
        if not options:
            tx.tx_json['obj'] = Exception('invalid options type')
            return tx
        if not options['type'] in RelationTypes:
            tx.tx_json['type'] = Exception('invalid relation type')
            return tx
        if options['type'] == 'trust':
            return self.__buildTrustSet(options, tx)
        elif options['type'] == 'authorize' or \
                options['type'] == 'freeze' or options['type'] == 'unfreeze':
            return self.__buildRelationSet(options, tx)
        tx.tx_json['msg'] = Exception('build relation set should not go here')
        return tx

    ##获得账号交易列表
    def requestAccountTx(self, options):
        data=[]
        request = Request(self, 'account_tx', None)
        if not isinstance(options, object):
            request.message['type'] = Exception('invalid options type')
            return request

        if not Wallet.isValidAddress(options['account']):
            request.message['account'] = Exception('account parameter is invalid')
            return request

        request.message['account'] = options['account']

        if options.__contains__('ledger_min') and Number(options['ledger_min']):
            request.message['ledger_index_min'] = Number(options['ledger_min'])
        else:
            request.message['ledger_index_min'] = 0
        if options.__contains__('ledger_max') and Number(options['ledger_max']):
            request.message['ledger_index_max'] = Number(options['ledger_max'])
        else:
            request.message['ledger_index_max'] = -1

        if options.__contains__('limit') and Number(options['limit']):
            request.message['limit'] = Number(options['limit'])

        if options.__contains__('offset') and Number(options['offset']):
            request.message['offset'] = Number(options['offset'])

        if options.__contains__('marker') and isinstance(options['marker'], 'object') and Number(options.marker['ledger']) != None and Number(
                options['marker']['seq']) != None:
            request.message['marker'] = options['marker']

        if options.__contains__('forward') and isinstance(options['forward'], 'boolean'):
            request.message['forward'] = options['forward']

        return request


    ##获得市场挂单列表
    def requestOrderBook(self,options):
        request = Request(self, 'book_offers',None)
        if not isinstance(options,object):
            request.message['type'] = Exception('invalid options type')
            return request

        # taker_gets = options['taker_gets'] or options['pays']
        if options.__contains__('taker_gets'):
            taker_gets = options['taker_gets']
        elif options.__contains__('pays'):
            taker_gets=options['pays']
        if not utils.isValidAmount0(taker_gets):
            request.message.taker_gets = Exception('invalid taker gets amount')
            return request

        # taker_pays = options['taker_pays'] or options['gets']
        if options.__contains__('taker_pays'):
            taker_pays = options['taker_pays']
        elif options.__contains__('gets'):
            taker_pays = options['gets']
        if not utils.isValidAmount0(taker_pays):
            request.message.taker_pays = Exception('invalid taker pays amount')
            return request

        if options.__contains__('limit'):
            if isinstance(options['limit'],int):
                options['limit'] = int(options['limit'])

        request.message['taker_gets'] = taker_gets
        request.message['taker_pays'] = taker_pays
        if options.__contains__('taker'):
            request.message['taker'] = options['taker']
        else:
            request.message['taker'] = Config.ACCOUNT_ONE
        # request.message['taker'] = options['taker'] if options['taker'] else utils['ACCOUNT_ONE']
        if options.__contains__('limit'):
            request.message['limit'] = options['limit']
        return request


