#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

  cloud-metric

  This program reads line protocol data from rabbitmq and inserts
  into influxdb.

  It should recover from RabbitMQ connection outages
  due to use of our RabbitSSL class, and will continue trying to
  insert a record if there is no HTTP response e.g. influx down.

"""
import time
import json
import requests
from requests.auth import HTTPBasicAuth
from modules.jsoncfg import JsonCfg
from modules.setlogger import SetLogger
from modules.rabbitssl import RabbitSSL


def validate_jobcard(jobcard):
    """ Ensure the jobcard is valid """
    if jobcard['hostname'] is None or \
       jobcard['hostname'] == '' or \
       jobcard['hostname'] == ' ' or \
       jobcard['jobcard'] is None or \
       jobcard['jobcard'] != 'cloud-metric' or \
       jobcard['linedata'] is None or \
       jobcard['linedata'] == '' or \
       jobcard['linedata'] == ' ':
        logger.info('[cloud-metric] Error - Jobcard could not be validated, dropping data')
        logger.debug('[cloud-metric] ' + str(jobcard))
        return False
    else:
        logger.debug('[cloud-metric] Validated jobcard for ' + jobcard['hostname'])
        return True


def influx_write(jobcard, db):
    """ Write line protocol data to influxdb """
    sess = requests.Session()
    url = 'http://' + cfg['influx_host'] + ':8086/write?db=' + db
    datapoints = 0
    for line in jobcard['linedata'].split('|'):
        if line != 'initial':
            write = False
            while write is False:
                try:
                    req = sess.post(url=url,
                                    auth=HTTPBasicAuth(cfg['influx_user'],
                                                       cfg['influx_pass']),
                                    data=line)
                    if req.status_code == 204 and cfg['log_debug'] == '1':
                        logger.debug('[cloud-metric] Inserted ' + line.split(',')[0] +
                                  ' for ' + jobcard['hostname'] + ' - ' +
                                  str(req.status_code))
                    if req.status_code != 204:
                        logger.info('[cloud-metric] Error inserting ' + line.split(',')[0] +
                                 ' for ' + jobcard['hostname'] + ' - ' +
                                 str(req.status_code))
                    write = True
                except Exception as ex:
                    write = False
                    logger.info('[cloud-metric] Unknown error, is influxdb down? Retrying in ' + str(cfg['metric_retry_delay']) + ' seconds')
                    logger.debug('[cloud-metric] Exception: ' + str(ex))
                    time.sleep(float(cfg['metric_retry_delay']))
            time.sleep(float(cfg['metric_backoff']))
            if write is True:
                datapoints += 1
    total_datapoints = datapoints + 1
    logger.info('[cloud-metric] Inserted ' + str(total_datapoints) + '/' + str(len(jobcard['linedata'].split('|'))) +' datapoints for ' +
             jobcard['hostname'])
    
def callback(ch, method, properties, body):
    """ Callback function processes rabbitmq message """
    jobcard = json.loads(body)
    validate = validate_jobcard(jobcard)
    if validate is True:
        if "1" == "2":
            db = jobcard['target']
        else:
            db = cfg['influx_default_db']
        influx_write(jobcard, db)
    else:
        print('bad')
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    """ Initialize class variables and start consuming """
    global cfg
    global logger
    cfg = JsonCfg('/opt/cloud/settings.json').load()['cloud-metric']
    logger = SetLogger(cfg).setup()
    rabbit = RabbitSSL(cfg)
    rabbit.connect()
    rabbit.consume(cfg['rabbit_consume_queue'], callback)

if __name__ == '__main__':
    main()
