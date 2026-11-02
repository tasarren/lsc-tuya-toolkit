import struct
import zlib

try:
    from Crypto.Cipher import AES
except Exception as exc:  # pragma: no cover - import-time environment guard
    raise SystemExit("Missing dependency: pycryptodome") from exc


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def derive_aes_key_from_enckey(enckey: bytes) -> bytes:
    if len(enckey) != 16:
        raise ValueError("tuya_enckey db must be exactly 16 bytes")
    w0, w1, w2, w3 = struct.unpack("<4I", enckey)
    rotated = struct.pack("<4I", w2, w3, w0, w1)
    out = bytearray(rotated)
    for index in range(0, 16, 2):
        out[index], out[index + 1] = out[index + 1], out[index]
    return bytes(out)


def pkcs7_pad(data: bytes, block: int = 16) -> bytes:
    pad = block - (len(data) & (block - 1))
    return data + bytes([pad]) * pad


def tal_get_actual_length_weak(data: bytes) -> int:
    if not data or (len(data) & 0xF) != 0:
        return -2
    pad = data[-1]
    if pad < 0x11:
        if pad < len(data):
            return len(data) - pad
        return -3
    return -2


def aes_ecb_encrypt(key: bytes, plain: bytes) -> bytes:
    return AES.new(key, AES.MODE_ECB).encrypt(pkcs7_pad(plain, 16))


def aes_ecb_decrypt(key: bytes, ciphertext: bytes) -> bytes:
    return AES.new(key, AES.MODE_ECB).decrypt(ciphertext)
