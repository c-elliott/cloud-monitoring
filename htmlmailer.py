#!/usr/bin/env python
from mailer import Mailer
from mailer import Message

send = 'noreply@monitoring.cloud'
rcpt = 'noc@somedomain.com'

trace = '''traceroute to google.com (216.58.213.110), 30 hops max, 60 byte packets
 1  a.router.com (xx.xx.xx.xx)  1.845 ms  2.048 ms  2.016 ms
 2  b.router.com (xx.xx.xx.xx)  0.389 ms  0.370 ms  0.524 ms
 3  c.router.com (xx.xx.xx.xx)  1.138 ms  1.411 ms  1.392 ms
 4  d.router.com (xx.xx.xx.xx)  0.670 ms  0.649 ms  0.623 ms'''

body = ('<p>This is an automated notification email from the cloud monitoring system.'
        '<br /><br />'
        'Please investigate the below as soon as possible:<br /><br />')
ack = '<a href="https://www.google.com">Click here</a>'
det = ('<strong>Server details:</strong>'
        '<ul>'
        '<li>Serverid: 456</li>'
        '<li>Acknowledge: ' + ack + '</li>'
        '</ul>')

data = ('<strong>Hostname:</strong> test.domain.com<br /><br />'
        '<strong>Alert:</strong> TCP Ports<br /><br />'
        '<strong>Reason:</strong> Port 27 failed<br /><br />'
        '<strong>Created:</strong> 25/02/2018 21:07:02 UTC<br /><br />'
        '<strong>Debug:</strong>'
        '<pre>' + trace + '</pre>')

foot = ('<hr><strong>DISCLAIMER</strong><br />'
        'Blah'
        'Blah</p>')

message = Message(From=send,
                  To=rcpt)
message.Subject = '[cloud-alert] TCP ports on test.domain.com'
message.Html = body + det + data + foot

sender = Mailer('127.0.0.1')
sender.send(message)
