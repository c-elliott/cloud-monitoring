#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

  A class to configure and return logger with PID
  and DD/MM/YY timestamp.

"""
import os
import logging


class SetLogger(object):
    def __init__(self, cfg):
        self.cfg = cfg
        self.pid = 'PID ' + str(os.getpid())
        if cfg['log_debug'] == '0':
            self.log_level = 'INFO'
        else:
            self.log_level = 'DEBUG'
        logging.basicConfig(filename=self.cfg['log_file'],
                            level=self.log_level,
                            format='%(asctime)s ' + self.pid + ': %(message)s',
                            datefmt='%d/%m/%y %H:%M:%S')
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    def setup(self):
        """ Return logger and create initial entry """
        logger = logging.getLogger(__name__)
        logger.info('[SetLogger] Started with loglevel ' + self.log_level)
        return logger
