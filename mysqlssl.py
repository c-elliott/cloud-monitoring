#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

  A class for interacting with MySQL over SSL. Includes continuous
  retry on connection failure until successful.

"""
import time
import MySQLdb
import ssl
import logging


class MySQLSSL(object):
    def __init__(self, cfg):
        try:
            self.cfg = cfg
            self.logger = logging.getLogger(__name__)
            self.ssl_opts = {
                "cert": self.cfg['mysql_ssl_cert'],
                "key": self.cfg['mysql_ssl_key'],
                "ca": self.cfg['mysql_ssl_ca'],
                "verify_cert": True
            }
        except Exception as ex:
            self.logger.info('[MySQLSSL] Error initializing class')
            self.logger.debug('[MySQLSSL] ' + str(ex))

    def connect(self):
        """ Connect to the server """
        try:
            self.connection = MySQLdb.connect(host=self.cfg['mysql_host'],
                                              user=self.cfg['mysql_user'],
                                              passwd=self.cfg['mysql_pass'],
                                              db=self.cfg['mysql_db'],
                                              ssl=self.ssl_opts)
            self.cursor = self.connection.cursor()
            self.logger.info('[MySQLSSL] Connected to '
                             + self.cfg['mysql_host'])
        except Exception:
            pass

    def disconnect(self):
        """ Disconnect from the server """
        try:
            self.connection.close()
        except Exception:
            pass

    def reconnect(self):
        """ Reconnect to be called upon failure """
        try:
            self.logger.info('[MySQLSSL] Connection unavailable. Trying reconnect \
                              in ' + str(self.cfg['mysql_retry_delay']) +
                             ' seconds')
            time.sleep(float(self.cfg['mysql_retry_delay']))
            self.disconnect()
            self.connect()
        except Exception as ex:
            logger.debug('[MySQLSSL] An unknown exception occured during \
                         reconnect')
            logger.debug('[MySQLSSL] ' + str(ex))

    def runquery(self, query, parms):
        """ Execute and commit a query """
        runquery = True
        while runquery is True:
            try:
                self.cursor.execute(query, parms)
                self.connection.commit()
                return self.cursor
                runquery = False
            except MySQLdb.OperationalError:
                self.reconnect()
            except AttributeError:
                self.reconnect()
            except Exception as ex:
                self.logger.info('[MySQLSSL] An unknown exception occurred')
                self.logger.debug('[MySQLSSL] ' + str(ex))
                self.reconnect()
