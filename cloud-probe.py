#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

  cloud-probe

  This program reads jobcards from rabbitmq validates this
  data and performs remote socket and http/https tests.

  It should recover from RabbitMQ and MySQL connection outages
  due to use of our RabbitSSL and MySQLSSL classes.

  A systemd unit file to run this as a service looks like this:

  - - - -

  [Unit]
  Description=cloud-probe
  After=network.target

  [Service]
  Type=simple
  User=cloud
  Group=cloud
  ExecStart=/opt/cloud/bin/cloud-probe.py 2>&1 &
  Restart=on-abort

  [Install]
  WantedBy=multi-user.target

  - - - -

"""
from modules.jsoncfg import JsonCfg
from modules.setlogger import SetLogger
from modules.rabbitssl import RabbitSSL
import json
import time
import socket
import subprocess

class Probe(object):
    def __init__(self, jobcard):
        self.cfg = cfg
        self.logger = logger
        self.rabbit = rabbit
        self.jobcard = jobcard

    def test_socket(self, hostname, port):
        try:
            newsocket = socket.socket()
            newsocket.settimeout(int(cfg['probe_socket_timeout']))
            newsocket.connect((str(hostname), int(port)))
            return 1
        except Exception as ex:
            self.logger.debug('[cloud-probe] Exception: ' + str(ex))
            return 0

    def validate_jobcard(self):
        """ Ensure the jobcard is valid """
        if self.jobcard['hostname'] is None or \
           self.jobcard['hostname'] == '' or \
           self.jobcard['hostname'] == ' ' or \
           self.jobcard['jobcard'] is None or \
           self.jobcard['jobcard'] != 'cloud-probe' or \
           self.jobcard['userid'] is None or \
           self.jobcard['userid'] == '' or \
           self.jobcard['userid'] == ' ':
            self.logger.info('[cloud-probe] Error - Jobcard could not be validated, dropping data')
            self.logger.debug('[cloud-probe] ' + jobcard)
            return False
        else:
            self.logger.info('[cloud-probe] Validated jobcard for ' + self.jobcard['hostname'])
            return True


    def process_tcp_ports(self):
        self.logger.info('[cloud-probe] Testing TCP ports for ' + self.jobcard['hostname'])
        tcp_ports = self.jobcard['tcp_ports'].split(',')
        res = ''
        for port in tcp_ports:
            test = self.test_socket(self.jobcard['hostname'], port)
            res += '{}|{} '.format(port, test)
            if test == 0:
                self.logger.info('[cloud-probe] Running TCP Traceroute on port ' + port + ' for ' + self.jobcard['hostname'])
                trace = subprocess.Popen(['tcptraceroute', self.jobcard['hostname'], port],stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                out, err = trace.communicate()
                traceroute = 'TCP Traceroute results for port {}\n'.format(port)
                traceroute += out
                self.jobcard.update({"debug_tcp_" + port: traceroute})
        self.jobcard.update({"tcp_ports_results": res})


    def process_udp_ports(self):
        self.logger.info('[cloud-probe] Testing UDP ports for ' + self.jobcard['hostname'])
        udp_ports = self.jobcard['udp_ports'].split(',')
        res = ''
        for port in udp_ports:
            test = self.test_socket(self.jobcard['hostname'], port)
            res += '{}|{} '.format(port, test)
        self.jobcard.update({"udp_ports_results": res})


    def send_completed_jobcard(self):
        self.jobcard.update({
            "updated": int(time.time()),
            "probe": self.cfg['rabbit_consume_queue']
        })
        self.rabbit.send(self.cfg['rabbit_inspector_queue'], self.jobcard)
        self.logger.info('[cloud-probe] Sent completed jobcard to inspector for ' + self.jobcard['hostname'])

def callback(ch, method, properties, body):
    """ Callback function processes rabbitmq message """
    jobcard = json.loads(body)
    probe = Probe(jobcard)
    validate = probe.validate_jobcard()
    if validate is True:
        if jobcard['tcp_ports'] is not None and jobcard['tcp_ports'] != '':
            probe.process_tcp_ports()
        if jobcard['udp_ports'] is not None and jobcard['udp_ports'] != '':
            probe.process_udp_ports()
        probe.send_completed_jobcard()
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    """ Initialize class variables and start consuming """
    global cfg
    global logger
    global rabbit
    cfg = JsonCfg('/opt/cloud/settings.json').load()['cloud-probe']
    logger = SetLogger(cfg).setup()
    rabbit = RabbitSSL(cfg)
    rabbit.connect()
    rabbit.consume(cfg['rabbit_consume_queue'], callback)

if __name__ == '__main__':
    main()
