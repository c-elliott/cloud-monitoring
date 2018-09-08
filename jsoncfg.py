#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

  A class to load configuration from a JSON file.

"""
import json


class JsonCfg(object):
    def __init__(self, configfile):
        try:
            with open(configfile) as file:
                self.cfg = json.load(file)
        except Exception:
            print('[JsonCfg] Failed to load configfile')

    def load(self):
        return self.cfg
