#!/usr/bin/env python

import ndnlog
import requests
import sys
import re
import time
import getopt
import json
from copy import deepcopy
from ndnlog import NdnLogToken
from enum import Enum
from collections import OrderedDict
from influxdb import InfluxDBClient

tsdbUri = 'http://192.168.99.100:4242/api/put?details'
tsdbJsonTemplate = { "metric": None, "timestamp": None, "value": None, "tags": {} }
# influxClient = None

metricPrefixRegex='(?P<superset>.+)\.(?P<set>.+)\.run\.(?P<run>\d)\.(?P<test_label>.*)\.(?P<client>consumer|producer)\.(?P<id>[A-z0-9]+)(\.from\.(?P<prod_id>[A-z0-9]+))'
startTimestamp = None
baseTimestamp = None
runNo = 0
metricsBatchSize = 10
metrics = []
timeOffset = 0
extractGeneric = True

#******************************************************************************
class IngestAdaptor(object):
	metricGenericTemplate = { 'metric' : None, 'timestamp': None, 'value': None, 'fields': {}, 'tags': {}}
	startTimestamp = None
	baseTimestamp = None
	timeOffset = 0
	writeCtr = 0
	lastWrite = 0
	metrics = []
	batchSize = 10
	dryRun = False
	metricWriteCounter = {}

	def __init__(self, timeOffset = 0):
		self.timeOffset = timeOffset
		self.baseTimestamp = 0

	def connect(self):
		pass

	def timeFunc(self, match):
		return 0

	def uniquefyTimestamps(self, metrics):
		timestamps = {}
		for metric in metrics:
			k = metric['timestamp']
			if k in timestamps.keys():
				timestamps[k] += 1
				metric['timestamp'] += timestamps[k]
				k = metric['timestamp']
			timestamps[k] = 0

	def writeBatch(self, metrics):
		pass

	def metricFunc(self, json):
		self.metrics.append(json)
		if len(self.metrics) == self.batchSize:
			self.writeBatch(self.metrics)
			self.writeCtr += self.batchSize
			self.metrics = []
			if self.writeCtr-self.lastWrite >= 1000 and not self.dryRun:
				print "wrote "+str(self.writeCtr-self.lastWrite)+" measurements. "+str(self.writeCtr)+" total."
				self.lastWrite = self.writeCtr
		if not json['metric'] in self.metricWriteCounter.keys():
			self.metricWriteCounter[json['metric']] = 0
		self.metricWriteCounter[json['metric']] += 1

	def finalize(self):
		if len(self.metrics) > 0:
			self.writeBatch(self.metrics)
			self.writeCtr += len(self.metrics)
			self.metrics = []
		print("wrote "+str(self.writeCtr)+" measurements total")
		for key in self.metricWriteCounter.keys():
			print(key+': '+str(self.metricWriteCounter[key]))

	@staticmethod
	def printMetric(json):
		sys.stdout.write(str(json['metric'])+" "+str(json['timestamp'])+" "+str(json['value']))
		for key in json['tags'].keys():
			sys.stdout.write(' '+str(key)+'='+str(json['tags'][key]))
		for key in json['fields'].keys():
			sys.stdout.write(' '+str(key)+'='+str(json['fields'][key]))
		sys.stdout.write('\n')

	@staticmethod
	def printMetrics(metrics):
		for m in metrics:
			IngestAdaptor.printMetric(m)

class InfluxAdaptor(IngestAdaptor):
	influxClient = None
	influxJsonTemplate = { "measurement": None, "time": None, "fields": { "value": None }, "tags": {} }
	batchSize = 1000
	metrics = []

	def __init__(self, user, password, dbname, timeOffset = 0, host = 'localhost', port = 8086):
		super(InfluxAdaptor, self).__init__(timeOffset)
		self.connect(host, port, user, password, dbname)
		self.baseTimestamp = 1234560000000 # millisec

	def connect(self, host, port, user, password, dbname):
		# user = 'parser'
		# password = 'letmein'
		# dbname = 'test'
		dbuser = 'parser'
		dbuser_password = 'letmein'
		self.influxClient = InfluxDBClient(host, port, user, password, dbname)

	def timeFunc(self, match):
		timestamp = int(match.group('timestamp'))
		if not self.startTimestamp:
			self.startTimestamp = timestamp
		unixTimestamp = self.baseTimestamp + (timestamp - self.startTimestamp)
		return unixTimestamp*1000000 # nanosec

	def writeBatch(self, metrics):
		self.uniquefyTimestamps(metrics)
		if self.dryRun:
			IngestAdaptor.printMetrics(metrics)
		else:
			batch = []
			for m in self.metrics:
				batch.append(self.toInfluxJson(m))
			self.influxClient.write_points(batch)

	def toInfluxJson(self, genericJson):
		influxJson = deepcopy(self.influxJsonTemplate)
		influxJson['measurement'] = genericJson['metric']
		influxJson['time'] = genericJson['timestamp']
		influxJson['fields']['value'] = genericJson['value']
		for key in genericJson['fields'].keys():
			influxJson['fields'][key] = genericJson['fields'][key]
		for key in genericJson['tags'].keys():
			influxJson['tags'][key] = genericJson['tags'][key]
		return influxJson

class TsdbAdaptor(IngestAdaptor):
	tsdbJsonTemplate = { "metric": None, "timestamp": None, "value": None, "tags": {} }

	def __init__(self, timeOffset = 0, tsdbUri = 'http://localhost:4242/api/put?details', batchSize = 20):
		super(TsdbAdaptor, self).__init__(timeOffset)
		self.tsdbUri = tsdbUri
		self.batchSize = batchSize
		self.baseTimestamp = 1234560000000

	def timeFunc(self, match):
		timestamp = int(match.group('timestamp'))
		if not self.startTimestamp:
			self.startTimestamp = timestamp
		unixTimestamp = self.baseTimestamp + (timestamp - self.startTimestamp) + self.timeOffset
		return unixTimestamp

	def writeBatch(self, metrics):
		if self.dryRun:
			IngestAdaptor.printMetrics(metrics)
		else:
			tsdbMetrics = []
			for m in metrics:
				tsdbMetrics.append(self.toTsdbJson(m))
			response = requests.post(url=self.tsdbUri, data=json.dumps(tsdbMetrics), headers={'content-type': 'application/json'})
			if response.status_code != 200:
				print('return code '+str(response.status_code)+'. aborting...')
				exit(1)

	def toTsdbJson(self, genericJson):
		tsdbJson = deepcopy(self.tsdbJsonTemplate)
		tsdbJson['metric'] = genericJson['metric']
		tsdbJson['value'] = genericJson['value']
		tsdbJson['timestamp'] = genericJson['timestamp']
		for key in genericJson['fields'].keys():
			tsdbJson['tags'][key] = genericJson['fields'][key]
		for key in genericJson['tags'].keys():
			tsdbJson['tags'][key] = genericJson['tags'][key]
		return tsdbJson

def makeMetricPath(prefix, metricName):
	global runNo
	if len(prefix) > 0:
		return prefix+"."+metricName.replace(" ", "_")
	return metricName.replace(" ", "_")

def makeCompMetric(componentsList = ()):
	return '.'.join(componentsList)

#******************************************************************************
def onInterest(timestamp, match, userData):
	global runNo, c
	onMetricFunc = userData['userData']['onMetricFunc']
	interestExpressMetric = deepcopy(IngestAdaptor.metricGenericTemplate)
	interestExpressMetric['tags'] = deepcopy(userData['userData']['tags'])
	interestExpressMetric['metric'] = makeMetricPath(userData['userData']['metricPrefix'], 'interest')
	interestExpressMetric['timestamp'] = timestamp
	interestExpressMetric['value'] = 1
	interestExpressMetric['fields']['segment'] = int(match.group('frame_no'))*100+ndnlog.segNoToInt(match.group('seg_no'))
	interestExpressMetric['fields']['run'] = runNo
	interestExpressMetric['tags']['thread'] = makeCompMetric((match.group('user'), match.group('stream'), match.group('thread')))
	interestExpressMetric['tags']['frame'] = makeCompMetric((match.group('frame_type'), match.group('data_type')))
	onMetricFunc(interestExpressMetric)

	segmentRequestMetric = deepcopy(IngestAdaptor.metricGenericTemplate)
	segmentRequestMetric['tags'] = deepcopy(userData['userData']['tags'])
	segmentRequestMetric['metric'] = makeMetricPath(userData['userData']['metricPrefix'], 'segment-req')
	segmentRequestMetric['timestamp'] = timestamp
	segmentRequestMetric['value'] = int(match.group('frame_no')) * 100 + ndnlog.segNoToInt(match.group('seg_no'))
	segmentRequestMetric['tags']['thread'] = makeCompMetric((match.group('user'), match.group('stream'), match.group('thread')))
	segmentRequestMetric['tags']['frame'] = makeCompMetric((match.group('frame_type'), match.group('data_type')))
	onMetricFunc(segmentRequestMetric)

	return True

def onInterestIncoming(timestamp, match, userData):
	global tsdbJsonTemplate, runNo
	onMetricFunc = userData['userData']['onMetricFunc']
	interestExpressMetric = deepcopy(IngestAdaptor.metricGenericTemplate)
	interestExpressMetric['tags'] = deepcopy(userData['userData']['tags'])
	interestExpressMetric['metric'] = makeMetricPath(userData['userData']['metricPrefix'], 'interest')
	interestExpressMetric['timestamp'] = timestamp
	interestExpressMetric['value'] = 1
	interestExpressMetric['fields']['segment'] = int(match.group('frame_no'))*100+ndnlog.segNoToInt(match.group('seg_no'))
	interestExpressMetric['fields']['run'] = runNo
	interestExpressMetric['tags']['staleness'] = match.group('istaleness')
	interestExpressMetric['tags']['thread'] = makeCompMetric((match.group('user'), match.group('stream'), match.group('thread')))
	interestExpressMetric['tags']['frame'] = makeCompMetric((match.group('frame_type'), match.group('data_type')))
	onMetricFunc(interestExpressMetric)

	segmentRequestMetric = deepcopy(IngestAdaptor.metricGenericTemplate)
	segmentRequestMetric['tags'] = deepcopy(userData['userData']['tags'])
	segmentRequestMetric['metric'] = makeMetricPath(userData['userData']['metricPrefix'], 'segment-req')
	segmentRequestMetric['timestamp'] = timestamp
	segmentRequestMetric['value'] = int(match.group('frame_no')) * 100 + ndnlog.segNoToInt(match.group('seg_no'))
	segmentRequestMetric['tags']['thread'] = makeCompMetric((match.group('user'), match.group('stream'), match.group('thread')))
	segmentRequestMetric['tags']['frame'] = makeCompMetric((match.group('frame_type'), match.group('data_type')))
	onMetricFunc(segmentRequestMetric)
	return True

def onTimeout(timestamp, match, userData):
	global tsdbJsonTemplate
	onMetricFunc = userData['userData']['onMetricFunc']
	timeoutMetric = deepcopy(IngestAdaptor.metricGenericTemplate)
	timeoutMetric['tags'] = deepcopy(userData['userData']['tags'])
	timeoutMetric['metric'] = makeMetricPath(userData['userData']['metricPrefix'], 'timeout')
	timeoutMetric['timestamp'] = timestamp
	timeoutMetric['value'] = 1
	timeoutMetric['fields']['segment'] = int(match.group('frame_no'))*100+ndnlog.segNoToInt(match.group('seg_no'))
	timeoutMetric['fields']['run'] = runNo
	timeoutMetric['tags']['frame'] = makeCompMetric((match.group('frame_type'), match.group('data_type')))
	timeoutMetric['tags']['thread'] = makeCompMetric((match.group('user'), match.group('stream'), match.group('thread')))
	onMetricFunc(timeoutMetric)
	return True

def onData(timestamp, match, userData):
	global tsdbJsonTemplate, runNo
	onMetricFunc = userData['userData']['onMetricFunc']
	dataMetric = deepcopy(IngestAdaptor.metricGenericTemplate)
	dataMetric['tags'] = deepcopy(userData['userData']['tags'])
	dataMetric['metric'] = makeMetricPath(userData['userData']['metricPrefix'], 'data')
	dataMetric['timestamp'] = timestamp
	dataMetric['value'] = 1
	dataMetric['fields']['segment'] = int(match.group('frame_no'))*100+ndnlog.segNoToInt(match.group('seg_no'))
	dataMetric['fields']['run'] = runNo
	dataMetric['tags']['data_type'] = match.group('data_type')
	dataMetric['tags']['thread'] = makeCompMetric((match.group('user'), match.group('stream'), match.group('thread')))
	onMetricFunc(dataMetric)

	segmentMetric = deepcopy(IngestAdaptor.metricGenericTemplate)
	segmentMetric['tags'] = deepcopy(userData['userData']['tags'])
	segmentMetric['metric'] = makeMetricPath(userData['userData']['metricPrefix'], 'segment')
	segmentMetric['timestamp'] = timestamp
	segmentMetric['value'] = int(match.group('frame_no'))*100+ndnlog.segNoToInt(match.group('seg_no'))
	segmentMetric['fields']['run'] = runNo
	segmentMetric['tags']['frame'] = makeCompMetric((match.group('frame_type'), match.group('data_type')))
	segmentMetric['tags']['thread'] = makeCompMetric((match.group('user'), match.group('stream'), match.group('thread')))
	onMetricFunc(segmentMetric)
	return True

def onChallengeData(timestamp, match, userData):
	global tsdbJsonTemplate, runNo
	onMetricFunc = userData['userData']['onMetricFunc']
	dataMetric = deepcopy(IngestAdaptor.metricGenericTemplate)
	dataMetric['tags'] = deepcopy(userData['userData']['tags'])
	dataMetric['metric'] = makeMetricPath(userData['userData']['metricPrefix'], 'data')
	dataMetric['timestamp'] = timestamp
	dataMetric['value'] = 1
	dataMetric['fields']['run'] = runNo
	dataMetric['fields']['segment'] = int(match.group('frame_no'))*100+ndnlog.segNoToInt(match.group('seg_no'))
	dataMetric['tags']['frame'] = makeCompMetric((match.group('frame_type'), match.group('data_type')))
	dataMetric['tags']['thread'] = makeCompMetric((match.group('user'), match.group('stream'), match.group('thread')))
	dataMetric['tags']['challenge'] = 1
	onMetricFunc(dataMetric)

	segmentMetric = deepcopy(IngestAdaptor.metricGenericTemplate)
	segmentMetric['tags'] = deepcopy(userData['userData']['tags'])
	segmentMetric['metric'] = makeMetricPath(userData['userData']['metricPrefix'], 'segment')
	segmentMetric['timestamp'] = timestamp
	segmentMetric['value'] = int(match.group('frame_no'))*100+ndnlog.segNoToInt(match.group('seg_no'))
	segmentMetric['fields']['run'] = runNo
	segmentMetric['tags']['frame'] = makeCompMetric((match.group('frame_type'), match.group('data_type')))
	segmentMetric['tags']['thread'] = makeCompMetric((match.group('user'), match.group('stream'), match.group('thread')))
	segmentMetric['tags']['challenge'] = 1
	onMetricFunc(segmentMetric)
	return True

def onRebuffering(timestamp, match, userData):
	global tsdbJsonTemplate, runNo
	onMetricFunc = userData['userData']['onMetricFunc']
	rebufferingMetric  = deepcopy(IngestAdaptor.metricGenericTemplate)
	rebufferingMetric['tags'] = deepcopy(userData['userData']['tags'])
	rebufferingMetric['metric'] = makeMetricPath(userData['userData']['metricPrefix'], 'rebuffering')
	rebufferingMetric['timestamp'] = timestamp
	rebufferingMetric['value'] = 1
	rebufferingMetric['fields']['run'] = runNo
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
	global runNo
	onMetricFunc = userData['userData']['onMetricFunc']
	keywordMetric = deepcopy(IngestAdaptor.metricGenericTemplate)
	keywordMetric['tags'] = deepcopy(userData['userData']['tags'])
	keywordMetric['metric'] = makeMetricPath(userData['userData']['metricPrefix'], match.group('keyword'))
	keywordMetric['fields']['run'] = runNo
	keywordMetric['timestamp'] = timestamp
	value = None
	try:
		value = float(match.group('value'))
	except:
		value = 1.0
		keywordMetric['tags']['value_str'] = match.group('value')
	keywordMetric['value'] = value
	onMetricFunc(keywordMetric)
	return True

def getConsumerActions(metricPrefix, tags, onJsonMetric, timeFunc):
	userData = { 'metricPrefix': metricPrefix, 'tags':tags.copy(), 'onMetricFunc':onJsonMetric }
	interestExpressRegex  = 'express\t'+ndnlog.NdnRtcNameRegexString
	interestExpressActions = {}
	interestExpressActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.debug.__str__(), '.*', interestExpressRegex)
	interestExpressActions['tfunc'] = timeFunc
	interestExpressActions['func'] = onInterest
	interestExpressActions['userdata'] = userData

	interestTimeoutRegex  = 'got timeout for '+ndnlog.NdnRtcNameRegexString
	interestTimeoutActions = {}
	interestTimeoutActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.debug.__str__(), '.*', interestTimeoutRegex)
	interestTimeoutActions['tfunc'] = timeFunc
	interestTimeoutActions['func'] = onTimeout
	interestTimeoutActions['userdata'] = userData

	dataReceivedRegex  = 'data '+ndnlog.NdnRtcNameRegexString
	dataReceivedActions = {}
	dataReceivedActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.debug.__str__(), '.*', dataReceivedRegex)
	dataReceivedActions['tfunc'] = timeFunc
	dataReceivedActions['func'] = onData
	dataReceivedActions['userdata'] = userData

	challengeReceivedRegex  = 'new challenge data '+ndnlog.NdnRtcNameRegexString
	challengeReceivedActions = {}
	challengeReceivedActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', dataReceivedRegex)
	challengeReceivedActions['tfunc'] = timeFunc
	challengeReceivedActions['func'] = onChallengeData
	challengeReceivedActions['userdata'] = userData

	rebufferingRegexString = 'rebuffering #(?P<rebuf_no>[0-9]+) seed (?P<seed>[0-9]+) key (?P<key>[0-9]+) delta (?P<delta>[0-9]+) curent w (?P<cur_w>[0-9-]+) default w (?P<default_w>[0-9-]+)'
	rebufferingActions = {}
	rebufferingActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.warning.__str__(), '.consumer-pipeliner', rebufferingRegexString)
	rebufferingActions['tfunc'] = timeFunc
	rebufferingActions['func'] = onRebuffering
	rebufferingActions['userdata'] = userData

	return [interestExpressActions, interestTimeoutActions, dataReceivedActions, challengeReceivedActions, rebufferingActions]

def getProducerActions(metricPrefix, tags, onJsonMetric, timeFunc):
	incomingInterestRegex = 'incoming interest for '+ndnlog.NdnRtcNameRegexString+' \((?P<istaleness>old|new)\)'
	incomingInterestActions = {}
	incomingInterestActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', incomingInterestRegex)
	incomingInterestActions['tfunc'] = timeFunc
	incomingInterestActions['func'] = onInterestIncoming
	incomingInterestActions['userdata'] = { 'metricPrefix': metricPrefix, 'tags':tags.copy(), 'onMetricFunc':onJsonMetric}

	cachedDataRegex = 'no pit entry '+ndnlog.NdnRtcNameRegexString
	cachedDataActions = {}
	cachedDataActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', cachedDataRegex)
	cachedDataActions['tfunc'] = timeFunc
	cachedDataActions['func'] = onData
	if len(metricPrefix) > 0: mp = metricPrefix+".cached"
	else: mp = "cached"
	cachedDataActions['userdata'] = { 'metricPrefix' : mp, 'tags':tags.copy(), "onMetricFunc":onJsonMetric}

	return [incomingInterestActions, cachedDataActions]

def parseForIngest(fileName, metricPrefix, tags, statKeywords, metricFunc, timeFunc):
	global extractGeneric
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
		keywordParsingActions['userdata'] = { 'metricPrefix': metricPrefix, 'tags': tags, 'onMetricFunc':metricFunc }

	if extractGeneric:
		if tags['client'] == 'consumer':
			parseActions = getConsumerActions(metricPrefix, tags, metricFunc, timeFunc)
		else:
			parseActions = getProducerActions(metricPrefix, tags, metricFunc, timeFunc)
	else:
		parseActions = []

	if statKeywords and len(statKeywords) > 0:
		parseActions.append(keywordParsingActions)

	ndnlog.parseLog(fileName, parseActions)

#******************************************************************************
def usage():
	print "usage: "+sys.argv[0]+" -f<consumer_log> -k<keywords> (-c|-p)"
	print "\toptions:"
	print "\t\t--influx-adaptor\tuse influx ungestion instead of OpenTSDB (default)"
	print "\t\t\tone should supply username, password and DB name for influx ingestion"
	print "\t\t--user\tusername for influx ingestion"
	print "\t\t--password\tpassword for influx ingestion"
	print "\t\t--db\tDB name for influx ingestion"
	print "\t\t--no-generic\tdo not extract generic metrics for producer/consumer (useful,"
	print "\t\t\twhen extracting stat metrics from same files iteratively"
	print "\t\t--dry-run\tprint results to the console instead of ingesting them to DB"
	print "\t\t--tags\tadditional tags that will be attached to each metric"
	print "\t\t--time-offset\ttime offset for correcting timestamps (useful for alignment consumer/producer logs)"

def main():
	global extractGeneric, tsdbUri
	keywords = None
	logFile = None
	isConsumer = None
	tags = {}
	dryRun = False
	needInfluxAdaptor = False
	timeOffset = 0
	host = 'localhost'
	tsdbPort = 4242
	influxPort = 8086
	port = None

	try:
		opts, args = getopt.getopt(sys.argv[1:], "idcpo:k:f:t:", ["no-generic", "user=", "password=", "db=", "influx-adaptor", "time-offset=", "consumer", "producer", "keywords=", "log=", "tags=", "dry-run", "port=", "host="])
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
		elif o in ("-t", "--tags"):
			tagsString = a
			tagPairs = tagsString.split(',')
			for pair in tagPairs:
				keyValue = pair.split('=')
				tags[keyValue[0]] = keyValue[1]
		elif o in ("-o", "--time-offset"):
			timeOffset = int(a)
		elif o in ("-i", "--influx-adaptor"):
			needInfluxAdaptor = True
		elif o in ("--user"):
			userName = a
		elif o in ("--password"):
			password = a
		elif o in ("--db"):
			dataBaseName = a
		elif o in ("--no-generic"):
			extractGeneric = False
		elif o in ("-d", "--dry-run"):
			dryRun = True
		elif o in ("--port"):
			port = int(a)
		elif o in ("--host"):
			host = a
		else:
			assert False, "unhandled option "+o
	if not logFile or isConsumer == None:
		usage();
		exit(1)
	if needInfluxAdaptor and not ('userName' in locals() or 'password' in locals() or 'dataBaseName' in locals()):
		print('please, supply username, password and db name for influx adaptor')
		usage()
		exit(1)

	if needInfluxAdaptor:
		if port: influxPort = port
		ingestAdaptor = InfluxAdaptor(user=userName, password=password, dbname=dataBaseName, timeOffset=timeOffset, host=host, port=influxPort)
	else:
		if port: tsdbPort = port
		ingestAdaptor = TsdbAdaptor(timeOffset=timeOffset, tsdbUri='http://{0}:{1}/api/put?details'.format(host, tsdbPort))

	tags['client'] = 'consumer' if isConsumer else 'producer'
	ingestAdaptor.dryRun = dryRun
	parseForIngest(logFile, '', tags, keywords, ingestAdaptor.metricFunc, ingestAdaptor.timeFunc)
	ingestAdaptor.finalize()

if __name__ == '__main__':
	main()
