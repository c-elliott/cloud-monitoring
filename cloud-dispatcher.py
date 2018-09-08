#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

  cloud-dispatcher

  This program retrieves a list of servers from a MySQL database,
  then submits jobcards to RabbitMQ for processing by remote
  probes.

  It should recover from RabbitMQ and MySQL connection
  outages when used with the RabbitSSL and MysqlSSL classes.
  due to use of our RabbitSSL and MySQLSSL classes.

"""
from modules.jsoncfg import JsonCfg
from modules.setlogger import SetLogger
from modules.rabbitssl import RabbitSSL
from modules.mysqlssl import MySQLSSL
import json
import time
import sys
import uuid

class Dispatcher(object):
    def __init__(self):
        self.cfg = cfg
        self.logger = logger
        self.rabbit = rabbit
        self.sql = sql

    def process_managed_ports(self):
        """ Create jobcards for managed servers not in maintenance mode """
        try:
            query = """SELECT serverid, userid, hostname, dispatch_timestamp, tcp_ports, udp_ports
                       FROM managed_list
                       WHERE state!=(%(state)s)"""
            parms = {"state": "3"}
            res = self.sql(query, parms)
            if res.rowcount >= 1:
                for row in res:
                    serverid = str(row[0])
                    userid = str(row[1])
                    hostname = row[2]
                    dispatch_timestamp = int(row[3])
                    tcp_ports = row[4]
                    udp_ports = row[5]
                    now = int(time.time())
                    elapsed = int(now - dispatch_timestamp)
                    if elapsed < int(cfg['dispatcher_managed_interval']):
                        logger.debug('[cloud-dispatcher] Skipping, elapsed time only ' + str(elapsed) + 's for ' + hostname)
                        continue
                    jobcard = {
                        "jobcard": 'cloud-probe',
                        "tracker": str(uuid.uuid4()),
                        "created": now,
                        "type": 'managed',
                        "serverid": serverid,
                        "userid": userid,
                        "hostname": hostname,
                        "tcp_ports": tcp_ports,
                        "udp_ports": udp_ports
                        }
                    self.rabbit.send(self.cfg['rabbit_probe1_queue'], jobcard)
                    self.rabbit.send(self.cfg['rabbit_probe2_queue'], jobcard)
                    query = """UPDATE managed_list
                               SET dispatch_timestamp=(%(dispatch_timestamp)s)
                               WHERE serverid=(%(serverid)s)"""
                    parms = {"dispatch_timestamp": now,
                             "serverid": serverid}
                    self.sql(query, parms)
                    logger.info('[cloud-dispatcher] Jobcard sent to probes for managed server ' + hostname)
        except Exception as ex:
                self.logger.info('[cloud-dispatcher] An unknown exception occurred')
                self.logger.info('[cloud-dispatcher] Exception: ' + str(ex))


def process():
    """ Call the dispatcher class """
    dispatcher = Dispatcher()
    while True:
        try:
            dispatcher.process_managed_ports()
            time.sleep(float(cfg['dispatcher_backoff']))
        except KeyboardInterrupt:
                logger.info('[cloud-dispatcher] Stopped processing due to keyboardinterrupt')
                sys.exit()


def main():
    """ Initialize class variables and start consuming """
    global cfg
    global logger
    global rabbit
    global sql
    cfg = JsonCfg('/opt/cloud/settings.json').load()['cloud-dispatcher']
    logger = SetLogger(cfg).setup()
    rabbit = RabbitSSL(cfg)
    rabbit.connect()
    mysql = MySQLSSL(cfg)
    mysql.connect()
    sql = mysql.runquery
    process()


if __name__ == '__main__':
    main()
