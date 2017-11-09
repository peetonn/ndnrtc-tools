#!/usr/bin/env python
# -*- coding: utf-8 -*- 

import ndnlog
import copy
import sys
import re
from ndnlog import NdnLogToken
import getopt

processStart = None
pubStart = None
allthreads={}
running = {'capture':None}
statTemplate = {'progress':0, 'capture':None, 'encoded':{}, 'threads_started':0, 'willpublish':None}
metrics = []

startTimestamp = None
# timestamp	capture	enc1	enc2	enc3	publish	process
def printStat(timestamp, name, stat):
	global allthreads, startTimestamp
	if not startTimestamp: startTimestamp = timestamp

	ntabs = {'capture':0, 'publish':4, 'process':5}
	tmp = dict((el,1+allthreads.keys().index(el)) for el in allthreads.keys())
	ntabs = dict(ntabs, **tmp)
	sys.stdout.write(str(timestamp-startTimestamp)+'\t')
	for i in range(0,ntabs[name]):
		sys.stdout.write('\t')
	sys.stdout.write(str(stat)+'\n')

count= 0
def onIncomingDetected(timestamp, match, userData):
	global metrics, count
	metric = copy.copy(statTemplate)
	metric['capture'] = timestamp
	metric['progress'] += 1
	for m in reversed(metrics):
		if m['progress'] >= 1:
			d = timestamp - m['capture']
			printStat(timestamp, 'capture', d)
			if m['progress'] == 1:
				m['capture'] = timestamp
			elif m['progress'] == 5:
				del metrics[metrics.index(m)]
			else:
				metrics.append(metric)
			break
	if len(metrics) == 0:
		metrics.append(metric)
	return True

def onBusyDetected(timestamp, match, userData):
	global metrics
	return True

def onEncodingDetected(timestamp, match, userData):
	global metrics, allthreads
	threadName = match.group('component_name')
	allthreads[threadName] = True
	threads = None
	metric = None
	for m in metrics:
		if m['progress'] == 1 or m['progress'] == 2:
			metric = m
			threads = m['encoded']
			metric['progress'] = 2
			break
	if not metric:
		raise Exception("something isn't right at "+str(timestamp))
	if not threadName in threads.keys():
		threads[threadName] = 0.
	if not threads[threadName]:
		threads[threadName] = timestamp
		metric['threads_started'] += 1
	else:
		d = timestamp-threads[threadName]
		printStat(timestamp, threadName, d)
		threads[threadName] = None
		metric['threads_started'] -= 1
		if metric['threads_started'] == 0:
			metric['progress'] = 3
	return True

def onPubStart(timestamp, match, userData):
	global metrics
	metric = None
	for m in metrics:
		if m['progress'] == 3:
			metric = m
			break;
	if not metric:
		raise Exception("something isn't right at "+str(timestamp))
	metric['willpublish'] = timestamp
	metric['progress'] += 1
	return True

def onPubEnd(timestamp, match, userData):
	global metrics
	i = 0
	metric = None
	for m in metrics:
		if m['progress'] == 4:
			metric = m
			break
		else: i+=1
	if not metric:
		print metrics
		raise Exception("something isn't right at "+str(timestamp))
	d = timestamp-m['willpublish']
	printStat(timestamp, 'publish', d)
	d = timestamp - m['capture']
	printStat(timestamp, 'process', d)
	metric['progress'] = 5
	if len(metrics) > 1:
		del metrics[metrics.index(metric)]
	return True

def usage():
	print 'usage: '+sys.argv[0] + ' -f <log_file>'

if __name__ == '__main__':
	logFile = None
	try:
		opts, args = getopt.getopt(sys.argv[1:], "f:", ["-file"])
	except getopt.GetoptError as err:
		print str(err)
		usage()
		sys.exit(2)
	for o, a in opts:
		if o in ("-f", "--file"):
			logFile = a
		else:
			assert False, "unhandled option "+o
	if not logFile:
		usage()
		exit(1)

	trackIncoming = {}
	trackIncoming['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.debug.__str__(), '.*', "incoming ARGB frame")
	trackIncoming['tfunc'] = ndnlog.DefaultTimeFunc
	trackIncoming['func'] = onIncomingDetected

	trackBusy = {}
	trackBusy['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.warning.__str__(), '.*', "busy publishing")
	trackBusy['tfunc'] = ndnlog.DefaultTimeFunc
	trackBusy['func'] = onBusyDetected

	trackEncStart = {}
	trackEncStart['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', "encoding")
	trackEncStart['tfunc'] = ndnlog.DefaultTimeFunc
	trackEncStart['func'] = onEncodingDetected

	trackEncEnd = {}
	trackEncEnd['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', "encoded")
	trackEncEnd['tfunc'] = ndnlog.DefaultTimeFunc
	trackEncEnd['func'] = onEncodingDetected

	trackEncDrop = {}
	trackEncDrop['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', "dropped")
	trackEncDrop['tfunc'] = ndnlog.DefaultTimeFunc
	trackEncDrop['func'] = onEncodingDetected

	trackPubStart = {}
	trackPubStart['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', "will publish")
	trackPubStart['tfunc'] = ndnlog.DefaultTimeFunc
	trackPubStart['func'] = onPubStart

	trackPubEnd = {}
	trackPubEnd['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.debug.__str__(), '.*', "⤷ published")
	trackPubEnd['tfunc'] = ndnlog.DefaultTimeFunc
	trackPubEnd['func'] = onPubEnd

	ndnlog.parseLog(logFile, [trackIncoming, trackBusy, trackEncStart, trackEncEnd, trackEncDrop, trackPubStart, trackPubEnd])

	print ('capture\t'+'\t'.join(allthreads.keys()) + '\tpub\tproc')
