# cloud-monitoring
The code is this repo was my first attempt at a "big" project in Python. It was meant to be a scalable, custom monitoring solution for Linux servers, including time series metrics down to 1 minute granularity, package version tracking, and remote connectivity testing.

It was never used for anything in production, I wanted to try and replicate the functionality of a much larger system I became responsible for at work.

All of the code is written by me from scratch, some is probably quite bad, but it was a great learning experience.

The main idea is:

* MySQL database contains servers to be monitored
* "Dispatcher" service, creates jobs for remote probes and writes to RabbitMQ
* "Probe" service reads jobs from rabbitmq, appends results and writes them to RabbitMQ
* "Inspector" service creates alerts, or writes metrics in LINE format to RabbitMQ
* "Metric" service reads metrics from RabbitMQ and writes them to InfluxDB
* "InventoryAPI" provides endpoint for an agent to submit metrics and package information
* "Inventory Push" agent posts local system and package data to an api
* Slack Bot for requesting data from the system - Unfinished
