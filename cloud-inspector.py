#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

  cloud-inspector

  This program provides core processing functionality for
  inventory, monitoring and metrics.

  It reads jobcards from rabbitmq, validates this data and
  updates the inventory. A new jobcard is created containing
  line protocol data for influxdb metrics, and sent to the
  appropriate queue.

  Remote monitoring results from probes are temporarily stored
  in mysql until results are recieved from two probes. If both
  probes return the same result, this data is considered reliable
  and will be used to create or resolve an alert.

  This is incomplete and it could be made more efficient with
  better validation, perhaps even generate LINE data for InfluxDB
  on the probes to save a hop. 

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

class Inspector(object):
    def __init__(self, jobcard):
        self.cfg = cfg
        self.logger = logger
        self.rabbit = rabbit
        self.sql = sql
        self.jobcard = jobcard

    def validate_jobcard(self):
        """ Perform basic validation of jobcard """
        if 'jobcard' in self.jobcard and \
           'hostname' in self.jobcard and \
           'created' in self.jobcard:
            if self.jobcard['hostname'] == '' or \
               self.jobcard['hostname'] == ' ' or \
               self.jobcard['jobcard'] != 'cloud-inventoryapi' and \
               self.jobcard['jobcard'] != 'cloud-probe' or \
               not isinstance(self.jobcard['created'], (int, long)):
                self.logger.info('[cloud-inspector] Error - Jobcard failed basic validation, dropping data')
                return False
            else:
                self.logger.debug('[cloud-inspector] Recieved jobcard appears to be valid')
                return True
        else:
            self.logger.info('[cloud-inspector] Error - Jobcard failed basic validation, dropping data')
            return False


    def lineappend_one(self, name, value):
        """ Append line protocol data for single key/value """
        if value is not None and value != '' and value != ' ':
            self.linedata += '|' \
                             + name \
                             + ',host=' + self.jobcard['hostname'] \
                             + ',clientid=' + self.userid \
                             + ' value=' + value \
                             + ' ' \
                             + self.jobcard['timestamp']

    def lineappend_two(self, name, value, extra, extravalue):
        """ Append line protocol data for double key/value """
        if value is not None and value != '' and value != ' ':
            self.linedata += '|' \
                             + name + ',host=' + self.jobcard['hostname'] \
                             + ',clientid=' + self.userid \
                             + ',' + extra + '=' + extravalue \
                             + ' value=' + value \
                             + ' ' \
                             + self.jobcard['timestamp']


    def process_inventory(self):
        """ Update inventory and create/resolve alerts """
        # Further validation of jobcard
        if self.jobcard['originip'] is not None and self.jobcard['token'] is not None:
            if self.jobcard['originip'] == '' or \
               self.jobcard['originip'] == ' ' or \
               self.jobcard['token'] != self.cfg['inventoryapi_token']:
                self.logger.info('[cloud-inspector] Error - Jobcard failed inventory validation, dropping data')
                self.logger.debug('[cloud-inspector] ' + str(self.jobcard))
        # Check server is provisioned
        query = """SELECT serverid, userid, state
                   FROM managed_list
                   WHERE hostname=(%(hostname)s)
                   AND ipaddr=(%(ipaddr)s)"""
        parms = {"hostname": self.jobcard['hostname'],
                 "ipaddr": self.jobcard['originip']}
        res = self.sql(query, parms)
        if res.rowcount == 1:
            for row in res:
                self.serverid = str(row[0])
                self.userid = str(row[1])
                state = row[2]
        else:
            self.logger.info('[cloud-inspector] Error - Server ' + self.jobcard['hostname'] + ' (' + self.jobcard['originip'] + ') is not provisioned - Dropping data')
            return False
        # Check if maintenance mode is enabled
        if state == 3:
            self.logger.debug('[cloud-inspector] Skipped inventory for ' + self.jobcard['hostname'] + ' - maintenance mode enabled')
            return False
        # Prepare load/memory/swap variables
        try:
            self.loadone = self.jobcard['loadavg'].split(' ')[0]
            self.loadfive = self.jobcard['loadavg'].split(' ')[1]
            self.loadfifteen = self.jobcard['loadavg'].split(' ')[2]
            if self.jobcard['memavailable'] == '' or self.jobcard['memavailable'] == ' ':
                self.memavailable = str(int(self.jobcard['memfree']) + int(self.jobcard['membuffers']) + int(self.jobcard['memfree']))
            else:
                self.memavailable = self.jobcard['memavailable']
            self.memavailablepercent = str(int(self.memavailable) / (int(self.jobcard['memtotal']) / 100))
            self.swapfreepercent = str(int(self.jobcard['swapfree']) / (int(self.jobcard['swaptotal']) / 100))
        except Exception as ex:
            self.logger.info('[cloud-inspector] Error - Exception when preparing inventory data')
            self.logger.info('[cloud-inspector] Exception: ' + str(ex))
        # Create a new row in managed_inventory if required
        query = """SELECT serverid
                   FROM managed_inventory
                   WHERE serverid=(%(serverid)s)"""
        parms = {"serverid": self.serverid}
        res = self.sql(query, parms)
        if res.rowcount != 1:
            query = """INSERT INTO managed_inventory
                       (serverid)
                       VALUES (%(serverid)s)"""
            parms = {"serverid": self.serverid}
            self.sql(query, parms)
        # Update managed_inventory with new data
        query = """UPDATE managed_inventory
                   SET cpumodel=(%(cpumodel)s),
                       cpunum=(%(cpunum)s),
                       loadone=(%(loadone)s),
                       loadfive=(%(loadfive)s),
                       loadfifteen=(%(loadfifteen)s),
                       uptime=(%(uptime)s),
                       uname=(%(uname)s),
                       redhatrelease=(%(redhatrelease)s),
                       memtotal=(%(memtotal)s),
                       memfree=(%(memfree)s),
                       membuffers=(%(membuffers)s),
                       memcached=(%(memcached)s),
                       memavailable=(%(memavailable)s),
                       memavailablepercent=(%(memavailablepercent)s),
                       swaptotal=(%(swaptotal)s),
                       swapfree=(%(swapfree)s),
                       swapfreepercent=(%(swapfreepercent)s),
                       numprocs=(%(numprocs)s),
                       netlisten=(%(netlisten)s),
                       diskusedspace=(%(diskusedspace)s),
                       diskusedinode=(%(diskusedinode)s),
                       pkg_openssl=(%(pkg_openssl)s),
                       pkg_opensshclient=(%(pkg_opensshclient)s),
                       pkg_opensshserver=(%(pkg_opensshserver)s),
                       pkg_httpd=(%(pkg_httpd)s),
                       pkg_php=(%(pkg_php)s),
                       pkg_xen=(%(pkg_xen)s),
                       pkg_vzctl=(%(pkg_vzctl)s),
                       pkg_cpanel=(%(pkg_cpanel)s),
                       pkg_push=(%(pkg_push)s)
                   WHERE serverid=(%(serverid)s)"""
        parms = {"cpumodel": self.jobcard['cpumodel'],
                 "cpunum": self.jobcard['cpunum'],
                 "loadone": self.loadone,
                 "loadfive": self.loadfive,
                 "loadfifteen": self.loadfifteen,
                 "uptime": self.jobcard['uptime'],
                 "uname": self.jobcard['uname'],
                 "redhatrelease": self.jobcard['release'],
                 "memtotal": self.jobcard['memtotal'],
                 "memfree": self.jobcard['memfree'],
                 "membuffers": self.jobcard['membuffers'],
                 "memcached": self.jobcard['memcached'],
                 "memavailable": self.memavailable,
                 "memavailablepercent": self.memavailablepercent,
                 "swaptotal": self.jobcard['swaptotal'],
                 "swapfree": self.jobcard['swapfree'],
                 "swapfreepercent": self.swapfreepercent,
                 "numprocs": self.jobcard['numprocs'],
                 "netlisten": self.jobcard['netlisten'],
                 "diskusedspace": self.jobcard['diskusedspace'],
                 "diskusedinode": self.jobcard['diskusedinode'],
                 "pkg_openssl": self.jobcard['pkg_openssl'],
                 "pkg_opensshclient": self.jobcard['pkg_opensshclient'],
                 "pkg_opensshserver": self.jobcard['pkg_opensshserver'],
                 "pkg_httpd": self.jobcard['pkg_httpd'],
                 "pkg_php": self.jobcard['pkg_php'],
                 "pkg_xen": self.jobcard['pkg_xen'],
                 "pkg_vzctl": self.jobcard['pkg_vzctl'],
                 "pkg_cpanel": self.jobcard['pkg_cpanel'],
                 "pkg_push": self.jobcard['pkg_push'],
                 "serverid": self.serverid}
        self.sql(query, parms)
        # Update managed_list with inventory_timestamp
        query = """UPDATE managed_list
                   SET inventory_timestamp=(%(inventory_timestamp)s)
                   WHERE serverid=(%(serverid)s)"""
        parms = {"inventory_timestamp": int(time.time()),
                 "serverid": self.serverid}
        self.sql(query, parms)
        self.logger.info('[cloud-inspector] Updated inventory for ' + self.jobcard['hostname'])
        return True


    def process_metric(self):
        """ Create metric jobcard from inventory data """
        self.linedata = 'initial'
        try:
            self.lineappend_one('linux_uptime', self.jobcard['uptime'])
            self.lineappend_one('linux_procs_total', self.jobcard['numprocs'])
            self.lineappend_one('linux_loadavg_1min', self.loadone)
            self.lineappend_one('linux_loadavg_5min', self.loadfive)
            self.lineappend_one('linux_loadavg_15min', self.loadfifteen)
            self.lineappend_one('linux_mem_total', self.jobcard['memtotal'])
            self.lineappend_one('linux_mem_free', self.jobcard['memfree'])
            self.lineappend_one('linux_mem_buffers', self.jobcard['membuffers'])
            self.lineappend_one('linux_mem_cached', self.jobcard['memcached'])
            self.lineappend_one('linux_mem_available', self.memavailable)
            self.lineappend_one('linux_mem_available_percent', self.memavailablepercent)
            self.lineappend_one('linux_swap_total', self.jobcard['swaptotal'])
            self.lineappend_one('linux_swap_free', self.jobcard['swapfree'])
            self.lineappend_one('linux_swap_free_percent', self.swapfreepercent)
            self.lineappend_one('linux_swap_used', str(int(self.jobcard['swaptotal']) - int(self.jobcard['swapfree'])))
            self.lineappend_one('linux_net_tcp_connections', self.jobcard['tcpnum'])
            self.lineappend_one('linux_net_udp_connections', self.jobcard['udpnum'])
            self.lineappend_one('linux_net_total_connections', str(int(self.jobcard['tcpnum']) + int(self.jobcard['udpnum'])))
            for interface in self.jobcard['netsar'].split(' '):
                self.lineappend_two('linux_net_rx_pck_sec', interface.split('|')[1], 'interface', interface.split('|')[0])
                self.lineappend_two('linux_net_tx_pck_sec', interface.split('|')[2], 'interface', interface.split('|')[0])
                self.lineappend_two('linux_net_total_pck_sec', str(float(interface.split('|')[2]) + float(interface.split('|')[2])), 'interface', interface.split('|')[0])
                self.lineappend_two('linux_net_rx_kB_sec', interface.split('|')[3], 'interface', interface.split('|')[0])
                self.lineappend_two('linux_net_tx_kB_sec', interface.split('|')[4], 'interface', interface.split('|')[0])
                self.lineappend_two('linux_net_total_kB_sec', str(float(interface.split('|')[3]) + float(interface.split('|')[3])), 'interface', interface.split('|')[0])
            for cpu in self.jobcard['mpstat'].split(' '):
                self.lineappend_two('linux_cpu_usr', cpu.split('|')[1], 'cpu', cpu.split('|')[0])
                self.lineappend_two('linux_cpu_nice', cpu.split('|')[2], 'cpu', cpu.split('|')[0])
                self.lineappend_two('linux_cpu_sys', cpu.split('|')[3], 'cpu', cpu.split('|')[0])
                self.lineappend_two('linux_cpu_iowait', cpu.split('|')[4], 'cpu', cpu.split('|')[0])
                self.lineappend_two('linux_cpu_irq', cpu.split('|')[5], 'cpu', cpu.split('|')[0])
                self.lineappend_two('linux_cpu_soft', cpu.split('|')[6], 'cpu', cpu.split('|')[0])
                self.lineappend_two('linux_cpu_steal', cpu.split('|')[7], 'cpu', cpu.split('|')[0])
                self.lineappend_two('linux_cpu_idle', cpu.split('|')[8], 'cpu', cpu.split('|')[0])
            for disk in self.jobcard['iostat'].split('\n'):
                self.lineappend_two('linux_disk_reads_sec', disk.split('|')[1], 'device', disk.split('|')[0])
                self.lineappend_two('linux_disk_writes_sec', disk.split('|')[2], 'device', disk.split('|')[0])
                self.lineappend_two('linux_disk_iops_sec', str(float(disk.split('|')[1]) + float(disk.split('|')[2])), 'device', disk.split('|')[0])
                self.lineappend_two('linux_disk_reads_kBs', disk.split('|')[3], 'device', disk.split('|')[0])
                self.lineappend_two('linux_disk_writes_kBs', disk.split('|')[4], 'device', disk.split('|')[0])
                self.lineappend_two('linux_disk_total_kBs', str(float(disk.split('|')[3]) + float(disk.split('|')[4])), 'device', disk.split('|')[0])
            for mount in self.jobcard['diskusedspace'].split(' '):
                self.lineappend_two('linux_disk_usedspace_percent', mount.split('|')[1] , 'mount', mount.split('|')[0])
            for mount in self.jobcard['diskusedinode'].split(' '):
                self.lineappend_two('linux_disk_usedinode_percent', mount.split('|')[1] , 'mount', mount.split('|')[0])
            self.logger.info('[cloud-inspector] Prepared line protocol data for server ' + self.jobcard['hostname'])
        except Exception as ex:
            self.logger.info('[cloud-inspector] Error preparing line protocol data for server ' + self.jobcard['hostname'])
            self.logger.info('[cloud-inspector] Exception: ' + str(ex))
            return False
        metricjobcard = {
            "jobcard": 'cloud-metric',
            "created": int(time.time()),
            "hostname": self.jobcard['hostname'],
            "clientid": self.userid,
            "linedata": self.linedata
        }
        self.rabbit.send(self.cfg['rabbit_metric_queue'], metricjobcard)
        # Update managed_list with metric_timestamp
        query = """UPDATE managed_list
                   SET metric_timestamp=(%(metric_timestamp)s)
                   WHERE serverid=(%(serverid)s)"""
        parms = {"metric_timestamp": int(time.time()),
                 "serverid": self.serverid}
        self.sql(query, parms)
        self.logger.info('[cloud-inspector] Sent new metric jobcard for server ' + self.jobcard['hostname'])


    def roundtrip_inventory(self):
        now = int(time.time())
        job = int(self.jobcard['created'])
        elapsed = now - job
        self.logger.info('[cloud-inspector] Roundtrip time on inventory jobcard for ' + self.jobcard['hostname'] + ' was ' + str(elapsed) + 's')
        
    def process_remote(self):
        """ Create/resolve alert """
        if 'serverid' not in self.jobcard:
            probe_serverid = '0'
        else:
            probe_serverid = self.jobcard['serverid']
        if 'remoteid' not in self.jobcard:
            probe_remoteid = '0'
        else:
            probe_remoteid = self.jobcard['remoteid']
        if 'tcp_ports_results' not in self.jobcard:
            probe_tcp_ports_results = '0'
        else:
            probe_tcp_ports_results = self.jobcard['tcp_ports_results']
        if 'udp_ports_results' not in self.jobcard:
            probe_udp_ports_results = '0'
        else:
            probe_udp_ports_results = self.jobcard['udp_ports_results']
        probe_debug = '0'
        # Check if we have jobcard result from other probe
        if 'tracker' in self.jobcard:
            query = """SELECT *
                       FROM inspector_pendingremote
                       WHERE tracker=(%(tracker)s)"""
            parms = {"tracker": self.jobcard['tracker']}
            res = self.sql(query, parms)
            if res.rowcount == 1:
                for row in res:
                    self.logger.info('[cloud-inspector] REMOTE ROW')
                    userid = str(row[0])
                    serverid = str(row[1])
                    remoteid = str(row[2])
                    tcp_ports_results = str(row[3])
                    udp_ports_results = str(row[4])
                    debug = str(row[5])
                    created = str(row[6])
                    if userid == str(self.jobcard['userid']) and \
                       serverid == str(probe_serverid) and \
                       remoteid == str(probe_remoteid) and \
                       tcp_ports_results == str(probe_tcp_ports_results) and \
                       udp_ports_results == str(probe_udp_ports_results) and \
                       debug == str(probe_debug):
                        self.logger.info('[cloud-inspector] REMOTE MATCH')
            # Add partial results into database
            else:
                query = """INSERT INTO inspector_pendingremote
                           (tracker,
                            probe,
                            userid,
                            serverid,
                            remoteid,
                            tcp_ports_results,
                            udp_ports_results,
                            debug,
                            created,
                            updated)
                           VALUES (%(tracker)s,
                                   %(probe)s,
                                   %(userid)s,
                                   %(serverid)s,
                                   %(remoteid)s,
                                   %(tcp_ports_results)s,
                                   %(udp_ports_results)s,
                                   %(debug)s,
                                   %(created)s,
                                   %(updated)s)"""
                parms = {"tracker": self.jobcard['tracker'],
                         "probe": self.jobcard['probe'],
                         "userid": self.jobcard['userid'],
                         "serverid": probe_serverid,
                         "remoteid": probe_remoteid,
                         "tcp_ports_results": probe_tcp_ports_results,
                         "udp_ports_results": probe_udp_ports_results,
                         "debug": probe_debug,
                         "created": self.jobcard['created'],
                         "updated": self.jobcard['updated']}
                self.sql(query, parms)


def callback(ch, method, properties, body):
    """ Callback function processes rabbitmq message """
    jobcard = json.loads(body)
    inspector = Inspector(jobcard)
    validate = inspector.validate_jobcard()
    inventory = False
    if validate is True and jobcard['jobcard'] == 'cloud-probe':
        inspector.process_remote()
    if validate is True and jobcard['jobcard'] == 'cloud-inventoryapi':
        inventory = inspector.process_inventory()
    if inventory is True:
        metric = inspector.process_metric()
        inspector.roundtrip_inventory()
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    """ Declare queues and start consuming jobcards """
    for queue in cfg['rabbit_queue_list']:
        rabbit.declare(queue)
    rabbit.consume(cfg['rabbit_consume_queue'], callback)


if __name__ == '__main__':
    """ Setup modules and call the main fuunction """
    cfg = JsonCfg('/opt/cloud/settings.json').load()['cloud-inspector']
    logger = SetLogger(cfg).setup()
    rabbit = RabbitSSL(cfg)
    rabbit.connect()
    mysql = MySQLSSL(cfg)
    mysql.connect()
    sql = mysql.runquery
    main()
