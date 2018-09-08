#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

  A class for AES string encryption and decryption.
  For AES-256 supply a 32-byte key.

"""
from Crypto.Cipher import AES
from Crypto import Random


class AESCrypt():
    def __init__(self):
        self.key = bytes(key)
        self.iv = Random.new().read(AES.block_size)
        self.cipher = AES.new(self.key, AES.MODE_CFB, self.iv)

    def encrypt(self, toencrypt):
        enc = self.iv + self.cipher.encrypt(bytes(toencrypt))
        res = enc.encode('hex')
        return res

    def decrypt(self, todecrypt):
        res = self.cipher.decrypt(todecrypt.decode('hex'))[len(self.iv):]
        return res
