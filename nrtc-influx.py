#!/usr/bin/env python

import ndnlog
import sys
from ndnlog import NdnLogToken
from enum import Enum
from collections import OrderedDict
import re
import time
import getopt
from influxdb import InfluxDBClient

influxJsonTemplate = { "measurement": None, "time": None, "fields": { "value": None }, "tags": {} }
influxClient = None

metricPrefixRegex='(?P<superset>.+)\.(?P<set>.+)\.run\.(?P<run>\d)\.(?P<test_label>.*)\.(?P<client>consumer|producer)\.(?P<id>[A-z0-9]+)(\.from\.(?P<prod_id>[A-z0-9]+))'
influxJsonTemplate['fields'] = {}
startTimestamp = None
baseTimestamp = None
runNo = 0

def timeFunc(match):
  global startTimestamp
  global baseTimestamp
  
  timestamp = int(match.group('timestamp'))

  if not startTimestamp:
    startTimestamp = timestamp
  if not baseTimestamp:
  	baseTimestamp = 0
    # baseTimestamp = 1450000000
    # baseTimestamp = int(time.time()*1000)
  
  unixTimestamp = baseTimestamp + (timestamp - startTimestamp)
  return unixTimestamp*1000000 # nanosec

def makeMetricPath(prefix, metricName):
	global runNo
	# return prefix + ".run"+str(runNo) + "." + 
	return metricName.replace(" ", "_")

def onInterest(timestamp, match, userData):
	global influxJsonTemplate, runNo
	onMetricFunc = userData['userData']['onMetricFunc']
	interestExpressMetric = influxJsonTemplate.copy()
	interestExpressMetric['fields'] = {}
	interestExpressMetric['tags'] = {}
	interestExpressMetric['measurement'] = makeMetricPath(userData['userData']['metricPrefix'], 'interest')
	interestExpressMetric['time'] = timestamp
	interestExpressMetric['fields']['value'] = 1
	interestExpressMetric['fields']['frame'] = int(match.group('frame_no'))
	interestExpressMetric['fields']['segment'] = ndnlog.segNoToInt(match.group('seg_no'))
	interestExpressMetric['tags']['run'] = runNo
	interestExpressMetric['tags']['frame_type'] = match.group('frame_type')
	interestExpressMetric['tags']['data_type'] = match.group('data_type')
	onMetricFunc(interestExpressMetric)
	return True

def onData(timestamp, match, userData):
	global influxJsonTemplate, runNo
	onMetricFunc = userData['userData']['onMetricFunc']
	dataReceivedMetric = influxJsonTemplate.copy()
	dataReceivedMetric['fields'] = {}
	dataReceivedMetric['tags'] = {}
	dataReceivedMetric['measurement'] = makeMetricPath(userData['userData']['metricPrefix'], 'data')
	dataReceivedMetric['time'] = timestamp
	dataReceivedMetric['fields']['value'] = 1
	dataReceivedMetric['fields']['frame'] = int(match.group('frame_no'))
	dataReceivedMetric['fields']['segment'] = ndnlog.segNoToInt(match.group('seg_no'))
	dataReceivedMetric['tags']['run'] = runNo
	dataReceivedMetric['tags']['frame_type'] = match.group('frame_type'),
	dataReceivedMetric['tags']['data_type'] = match.group('data_type')
	onMetricFunc(dataReceivedMetric)
	return True

def onRebuffering(timestamp, match, userData):
	global influxJsonTemplate, runNo
	onMetricFunc = userData['userData']['onMetricFunc']
	rebufferingMetric  = influxJsonTemplate.copy()
	rebufferingMetric['fields'] = {}
	rebufferingMetric['tags'] = {}
	rebufferingMetric['measurement'] = makeMetricPath(userData['userData']['metricPrefix'], 'rebuffering')
	rebufferingMetric['time'] = timestamp
	rebufferingMetric['tags']['run'] = runNo
	rebufferingMetric['fields']['value'] = 1
	rebufferingMetric['fields']['no'] = int(match.group('rebuf_no'))
	rebufferingMetric['fields']['seed'] = int(match.group('seed'))
	rebufferingMetric['fields']['key_no'] = int(match.group('key'))
	rebufferingMetric['fields']['delta_no'] = int(match.group('delta'))
	rebufferingMetric['fields']['cur_lambda'] = int(match.group('cur_w'))
	rebufferingMetric['fields']['def_lambda'] = int(match.group('default_w'))
	runNo += 1
	onMetricFunc(rebufferingMetric)
	return True

def onKeywordFound(timestamp, match, userData):
	global influxJsonTemplate, runNo
	onMetricFunc = userData['userData']['onMetricFunc']
	keywordMetric = influxJsonTemplate.copy()
	keywordMetric['fields'] = {}
	keywordMetric['tags'] = {}
	keywordMetric['measurement'] = makeMetricPath(userData['userData']['metricPrefix'], match.group('keyword'))
	keywordMetric['tags']['run'] = runNo
	keywordMetric['time'] = timestamp
	value = None
	try:
		value = float(match.group('value'))
	except:
		value = 1.0
		keywordMetric['tags']['value_str'] = match.group('value')
	keywordMetric['fields']['value'] = value
	onMetricFunc(keywordMetric)
	return True

def getConsumerActions(metricPrefix, onJsonMetric):
	interestExpressRegex  = 'express\t'+ndnlog.NdnRtcNameRegexString
	interestExpressActions = {}
	interestExpressActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.debug.__str__(), '.*', interestExpressRegex)
	interestExpressActions['tfunc'] = timeFunc
	interestExpressActions['func'] = onInterest
	interestExpressActions['userdata'] = { 'metricPrefix': metricPrefix, 'onMetricFunc':onJsonMetric }

	dataReceivedRegex  = 'data '+ndnlog.NdnRtcNameRegexString
	dataReceivedActions = {}
	dataReceivedActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.debug.__str__(), '.*', dataReceivedRegex)
	dataReceivedActions['tfunc'] = timeFunc
	dataReceivedActions['func'] = onData
	dataReceivedActions['userdata'] = { 'metricPrefix': metricPrefix, 'onMetricFunc':onJsonMetric }

	rebufferingRegexString = 'rebuffering #(?P<rebuf_no>[0-9]+) seed (?P<seed>[0-9]+) key (?P<key>[0-9]+) delta (?P<delta>[0-9]+) curent w (?P<cur_w>[0-9-]+) default w (?P<default_w>[0-9-]+)'
	rebufferingActions = {}
	rebufferingActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.warning.__str__(), '.consumer-pipeliner', rebufferingRegexString)
	rebufferingActions['tfunc'] = timeFunc
	rebufferingActions['func'] = onRebuffering
	rebufferingActions['userdata'] = {'metricPrefix': metricPrefix, 'onMetricFunc':onJsonMetric }

	return [interestExpressActions, dataReceivedActions, rebufferingActions]

def getProducerActions(metricPrefix, onJsonMetric):
	return []

def parseForInflux(fileName, isConsumer, metricPrefix, statKeywords, onJsonMetric):
	if statKeywords:
		keywordNames = ""
		for keyword in statKeywords:
			if statKeywords.index(keyword) != len(statKeywords)-1:
				keywordNames += keyword.rstrip()+"|"
			else:
				keywordNames += keyword.rstrip()

		keywordRegexString = "(?P<keyword>"+keywordNames+")\s(?P<value>\S+)\s?"
		keywordParsingActions = {}
		keywordParsingActions['pattern'] = ndnlog.compileNdnLogPattern('.*', '.*', keywordRegexString)
		keywordParsingActions['tfunc'] = timeFunc
		keywordParsingActions['func'] = onKeywordFound
		keywordParsingActions['userdata'] = { 'metricPrefix': metricPrefix, 'onMetricFunc':onJsonMetric }

	if isConsumer:
		parseActions = getConsumerActions(metricPrefix, onJsonMetric)
	else:
		parseActions = getProducerActions(metricPrefix, onJsonMetric)

	if statKeywords and len(statKeywords) > 0:
		parseActions.append(keywordParsingActions)

	ndnlog.parseLog(fileName, parseActions)

def printJson(json):
	print json

def writeJson(json):
	global influxClient
	print "writing json "+str(json)[0:100]+"..."
	influxClient.write_points([json])

def connectInfluxDB():
	global influxClient
	user = 'parser'
	password = 'letmein'
	dbname = 'test'
	dbuser = 'parser'
	dbuser_password = 'letmein'
	influxClient = InfluxDBClient('localhost', 8086, user, password, 'test')

def usage():
	print "usage: "+sys.argv[0]+" -f<consumer_log> -k<keywords> (-c|-p)"

json_body = [
        {
            "measurement": "cpu_load_short",
            "tags": {
                "host": "server01",
                "region": "us-west"
            },
            "time": "2009-11-10T23:00:00Z",
            "fields": {
                "value": 0.64
            }
        }
    ]

def main():
	global json_body, influxJsonTemplate
	connectInfluxDB()
	# influxClient.create_database('delme')
	# writeJson(json_body)
	# exit(0)
	keywords = None
	logFile = None
	isConsumer = None
	metricPrefix = ""
	try:
		opts, args = getopt.getopt(sys.argv[1:], "cpk:f:r:", ["consumer", "producer", "keywords=", "log=", "prefix="])
	except getopt.GetoptError as err:
		print str(err)
		usage()
		exit(2)
	for o, a in opts:
		if o in ("-f", "--log"):
			logFile = a
		elif o in ("-k", "--keywords"):
			keywords = a.split(',')
		elif o in ("-c", "--consumer"):
			isConsumer = True
		elif o in ("-p", "--producer"):
			isConsumer = False
		elif o in ("-r", "--prefix"):
			metricPrefix = a
		else:
			assert False, "unhandled option "+o
	if not logFile or isConsumer == None:
		usage();
		exit(1)
	
	p = re.compile(metricPrefixRegex)
	m = p.match(metricPrefix)
	if m:
		influxJsonTemplate['tags']['test_superset'] = m.group('superset')
		influxJsonTemplate['tags']['test_set'] = m.group('set')
		influxJsonTemplate['tags']['test_run'] = m.group('run')
		influxJsonTemplate['tags']['test_label'] = m.group('test_label')
		influxJsonTemplate['tags']['client'] = m.group('client')
		influxJsonTemplate['tags']['client_id'] = m.group('id')
		if m.group('client') == 'consumer':
			influxJsonTemplate['tags']['producer'] = m.group('prod_id')

	parseForInflux(logFile, isConsumer, '', keywords, writeJson)

if __name__ == '__main__':
	main()


