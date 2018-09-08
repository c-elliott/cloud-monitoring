#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""

  cloud-inventoryapi

  This program implements a HTTPS API using the Falcon framework
  and should be called using Gunicorn. It is used to recieve POST
  requests from the inventory-push monitoring agent.

  A systemd unit file to run this as a service looks like this:
 
  - - - -

  [Unit]
  Description=cloud-inventoryapi (gunicorn)
  After=network.target

  [Service]
  User=cloud
  Group=cloud
  WorkingDirectory=/opt/cloud/bin
  ExecStart=/usr/bin/gunicorn -w 4 --max-requests 50 -t 60 --backlog 128 --bind 127.0.0.1:8000 cloud-inventoryapi:app

  [Install]
  WantedBy=multi-user.target

  - - - -

  You could then place this behind a loadbalancer, otherwise using
  Nginx as a reverse-proxy would be a good idea.

"""

from modules.jsoncfg import JsonCfg
from modules.setlogger import SetLogger
from modules.rabbitssl import RabbitSSL
import falcon
import time
import json

# A class where we will handle inventory requests
class InventoryResource(object):
    def on_post(self, req, resp):

        # Check if we recieved some data
        try:
            raw_json = req.stream.read()
        except Exception as ex:
            raise falcon.HTTPError(falcon.HTTP_400, ex.message)

        # Check that we recieved valid JSON
        try:
            result_json = json.loads(raw_json, encoding='utf-8')
            logger.debug('[cloud-inventoryapi] JSON: ' + str(result_json))
        except ValueError:
            resp.status = falcon.HTTP_400
            resp.body = 'INTERNALAPI-INVALIDJSON'

        # Get real originating IP of the request
        originip = req.access_route[0]

        # Check that we have a valid token, hostname and originip
        try:
            if result_json['token'] == cfg['inventoryapi_token'] and \
                result_json['hostname'] is not None and \
                result_json['hostname'] != "" and \
                originip is not None and \
                originip != "":

                # Add jobcard title and originating IP and created time
                result_json.update({
                    "created": int(time.time()),
                    "jobcard": "cloud-inventoryapi",
                    "originip": originip
                })

                # Log the valid request
                logger.info('[cloud-inventoryapi] Valid JSON from ' + result_json['hostname'] + ' (' + originip + ')' ) 

                # Send jobcard to RabbitMQ
                try:
                    rabbit.connect()
                    rabbit.send(cfg['rabbit_queue_inspector'], result_json)
                    logger.info('[cloud-inventoryapi] Jobcard sent to inspector for ' + result_json['hostname'] + ' (' + originip + ')' )
                    rabbit.disconnect()

                    # Return success to client
                    resp.status = falcon.HTTP_202
                    resp.body = 'API-OK'
                except Exception as ex:
                    logger.debug('[cloud-inventoryapi] Exception: ' + str(ex))
                    raise Exception
            else:
                # Log invalid request and raise generic exception
                logger.info('[cloud-inventoryapi] Invalid data from ip ' + originip)
                raise Exception
        except:
            resp.status = falcon.HTTP_500
            resp.body = 'INTERNALAPI-PROCESSERROR'
            #raise falcon.HTTPError(falcon.HTTP_500, 'API-PROCESSERROR')


if __name__ == '__main__':
    print('This program should be called by gunicorn, not directly.')
    sys.exit()

cfg = JsonCfg('/opt/cloud/settings.json').load()['cloud-inventoryapi']
logger = SetLogger(cfg).setup()
rabbit = RabbitSSL(cfg)
app = api = falcon.API()
inventory = InventoryResource()
api.add_route('/inventory', inventory)
