#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

  A class for interacting with RabbitMQ over SSL, includes continuous
  retry on connection failure until successful.

"""
import time
import pika
import ssl
import json
import logging


class RabbitSSL(object):
    def __init__(self, cfg):
        try:
            self.cfg = cfg
            logging.getLogger("pika").propagate = False
            self.logger = logging.getLogger(__name__)
            ssl_opts = {
                "ca_certs": self.cfg['rabbit_ssl_ca'],
                "certfile": self.cfg['rabbit_ssl_cert'],
                "keyfile": self.cfg['rabbit_ssl_key'],
                "cert_reqs": ssl.CERT_REQUIRED,
                "ssl_version": ssl.PROTOCOL_TLSv1_2
            }
            port = int(cfg['rabbit_port'])
            creds = pika.PlainCredentials(cfg['rabbit_user'],
                                          cfg['rabbit_pass'])
            self.parms = pika.ConnectionParameters(host=cfg['rabbit_host'],
                                                   port=port,
                                                   heartbeat_interval=0,
                                                   credentials=creds,
                                                   ssl=True,
                                                   ssl_options=ssl_opts)
        except AttributeError:
            self.logger.info('[RabbitSSL] Invalid configuration, init failed')
        except Exception as ex:
            self.logger.info('[RabbitSSL] Error during class init')
            self.logger.debug('[RabbitSSL] ' + str(ex))

    def connect(self):
        """ Connect to the server """
        try:
            self.connection = pika.BlockingConnection(self.parms)
            self.channel = self.connection.channel()
            self.logger.info('[RabbitSSL] Connected to '
                             + self.cfg['rabbit_host'])
        except pika.exceptions.ConnectionClosed:
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
            self.logger.info('[RabbitSSL] Connection unavailable. Trying reconnect \
                              in ' + str(self.cfg['rabbit_retry_delay'])
                             + ' seconds')
            time.sleep(float(self.cfg['rabbit_retry_delay']))
            self.disconnect()
            self.connect()
        except Exception as ex:
            logger.debug('[RabbitSSL] Unknown exception during reconnect')
            logger.debug('[RabbitSSL] ' + str(ex))

    def declare(self, queue):
        """ Creates a durable queue if it does not exist """
        declare = False
        while declare is False:
            try:
                self.channel.queue_declare(queue=queue, durable=True)
                declare = True
                self.logger.info('[RabbitSSL] Declared queue ' + queue)
            except pika.exceptions.ConnectionClosed:
                self.reconnect()
            except AttributeError:
                self.reconnect()

    def send(self, queue, message):
        """ Sends a persistent message onto a queue """
        sent = False
        while sent is False:
            try:
                msg = json.dumps(message)
                self.channel.confirm_delivery()
                if self.channel.basic_publish(exchange='',
                                              routing_key=queue,
                                              body=msg,
                                              mandatory=True,
                                              properties=pika.BasicProperties(
                                                  delivery_mode=2)):
                    sent = True
                    self.logger.debug('[RabbitSSL]: Sent message to queue '
                                      + queue)
                else:
                    self.logger.info('[RabbitSSL]: Failed sending message to queue '
                                     + queue)
                    sent = False
            except pika.exceptions.ConnectionClosed:
                self.reconnect()
            except AttributeError:
                self.reconnect()

    def consume(self, queue, callback):
        """ Listens for messages and sends to callback function """
        consuming = True
        while consuming is True:
            try:
                self.channel.basic_qos(prefetch_count=int(
                                          self.cfg['rabbit_prefetch']))
                self.channel.basic_consume(callback, queue=queue, no_ack=False)
                self.logger.info('[RabbitSSL] Start consuming messages on queue ' + queue)
                self.channel.start_consuming()
            except pika.exceptions.ConnectionClosed:
                    self.reconnect()
            except AttributeError:
                    self.reconnect()
            except KeyboardInterrupt:
                self.logger.info('[RabbitSSL] Stopped consuming messages due to keyboardinterrupt')
                self.channel.stop_consuming()
                consuming = False
            except Exception as ex:
                self.logger.info('[RabbitSSL] An unknown exception occurred')
                self.logger.debug('[RabbitSSL] ' + str(ex))
                self.reconnect()
