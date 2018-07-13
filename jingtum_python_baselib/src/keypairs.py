# coding=gbk
"""
 * User: ������
 * Date: 2018/5/16
 * Time: 11:25
 * Description: Ǯ��������ģ��
"""
import hashlib
from binascii import hexlify, unhexlify
import os, time
from random import randint
from ecdsa import curves, SigningKey
from jingtum_python_baselib.src.utils import *
from jingtum_python_baselib.src.base58 import base58

SEED_PREFIX = 33
ACCOUNT_PREFIX = 0
alphabet = 'jpshnaf39wBUDNEGHJKLM4PQRST7VWXYZ2bcdeCg65rkm8oFqi1tuvAxyz'

def hash256(data):
    """
        operation twice
    """
    one256 = unhexlify(hashlib.sha256(data).hexdigest())
    return hashlib.sha256(one256).hexdigest()

def sha256(bytes):
    hash = hashlib.sha256()
    hash.update(bytes)
    return hash.digest()

"""
 * decode encoded input,
 * too small or invalid checksum will throw exception
 * @param {integer} version
 * @param {string} input
 * @returns {buffer}
 * @private
"""
def decodeAddress(version, input):
    s = base58(alphabet)
    bytes = s.decode(input)
    if not bytes or bytes[0] != version or len(bytes) < 5:
        raise Exception('invalid input size')
    computed = sha256(sha256(bytearray(bytes[0:-4])))[0:4]
    checksum = bytes[-4:]
    i = 0
    #print('computed[0] is ', computed[0])
    while i != 4:
        if (computed[i] != checksum[i]):
            raise Exception('invalid checksum')
        i += 1
    return bytes[1:-4]

def get_str(l):
    sss = ""
    while(l>0):
        try:
            l, b = divmod(l, 58)
            sss +=  alphabet[b:b+1]
        except Exception:
            print("get_str error[%s]."%str(b))
            return None
    return sss[::-1]

"""
 * generate random bytes and encode it to secret
 * @returns {string}
"""
def get_secret(extra="FSQF5356dsdsqdfEFEQ3fq4q6dq4s5d"):
    """
        get a random secret
    """
    try:
        rnd = hexlify(os.urandom(256))
        tim = time.time()
        data = "%s%s%s%s"%(rnd, tim, randint(100000000000, 1000000000000), extra)
        res = int(hash256(data.encode("utf8")), 16)
        seed = '21' + str(res)[:32]
        secretKey = hash256(unhexlify(seed))[:8]
        l = int(seed + secretKey, 16)
    except Exception as e:
        print("get_secret error[%s]."%str(e))
        return None

    return get_str(l)


def root_key_from_seed(seed):
    """This derives your master key the given seed.

    """
    seq = 0
    while True:
        private_gen = from_bytes(first_half_of_sha512(
            b''.join([seed, to_bytes(seq, 4)])))
        seq += 1
        if curves.SECP256k1.order >= private_gen:
            break

    public_gen = curves.SECP256k1.generator * private_gen

    # Now that we have the private and public generators, we apparently
    # have to calculate a secret from them that can be used as a ECDSA
    # signing key.
    secret = i = 0
    public_gen_compressed = ecc_point_to_bytes_compressed(public_gen)
    while True:
        secret = from_bytes(first_half_of_sha512(
            b"".join([
                public_gen_compressed, to_bytes(0, 4), to_bytes(i, 4)])))
        i += 1
        if curves.SECP256k1.order >= secret:
            break
    secret = (secret + private_gen) % curves.SECP256k1.order

    # The ECDSA signing key object will, given this secret, then expose
    # the actual private and public key we are supposed to work with.
    key = SigningKey.from_secret_exponent(secret, curves.SECP256k1)
    # Attach the generators as supplemental data
    key.private_gen = private_gen
    #print('private_gen is ', private_gen)
    key.public_gen = public_gen
    #print('public_gen is ', public_gen)
    return key

def first_half_of_sha512(*bytes):
    """As per spec, this is the hashing function used."""
    hash = hashlib.sha512()
    for part in bytes:
        hash.update(part)
    return hash.digest()[:256//8]

def ecc_point_to_bytes_compressed(point, pad=False):
    """
    Implemented as a prototype extension
    ``sjcl.ecc.point.prototype.toBytesCompressed`` in ``sjcl-custom``.

    Also implemented as ``KeyPair.prototype._pub_bits``, though in
    that case it explicitly first pads the point to the bit length of
    the curve prime order value.
    """

    header = b'\x02' if point.y() % 2 == 0 else b'\x03'
    bytes = to_bytes(
        point.x(),
        curves.SECP256k1.order.bit_length()//8 if pad else None)
    return b"".join([header, bytes])

"""
 * derive keypair from secret
 * @param {string} secret
 * @returns {{privateKey: string, publicKey: *}}
"""
def deriveKeyPair(secret):
    prefix = '00'
    entropy = __decode(SEED_PREFIX, secret)
    print('entropy is first', entropy)
    entropy = base58x.decode(secret)[1:-4]
    print('entropy is ', entropy)
    privateKey = prefix + hex(derivePrivateKey(entropy)).replace('0x', '').upper()
    publicKey = bytesToHex(ec.keyFromPrivate(privateKey[2]).getPublic().encodeCompressed())
    return {privateKey: privateKey, publicKey: publicKey}


"""
 * devive keypair from privatekey
"""
def deriveKeyPairWithKey(key):
    privateKey = key
    publicKey = bytesToHex(ec.keyFromPrivate(key).getPublic().encodeCompressed())
    return {privateKey: privateKey, publicKey: publicKey}

def parse_seed(secret):
    """Your Jingtum secret is a seed from which the true private key can
    be derived.
    """
    assert secret[0] == 's'
    return JingtumBaseDecoder.decode(secret)

def get_jingtum_from_pubkey(pubkey):
    """Given a public key, determine the Jingtum address.
    """
    ripemd160 = hashlib.new('ripemd160')
    ripemd160.update(hashlib.sha256(pubkey).digest())
    return JingtumBaseDecoder.encode(ripemd160.digest())

def get_jingtum_from_secret(seed):
    """Another helper. Returns the first jingtum address from the secret."""
    print('seed is ', seed)
    key = root_key_from_seed(parse_seed(seed))
    pubkey = ecc_point_to_bytes_compressed(key.privkey.public_key.point, pad=True)
    print('got pubkey is ', pubkey)
    return get_jingtum_from_pubkey(pubkey)



#get_secret()