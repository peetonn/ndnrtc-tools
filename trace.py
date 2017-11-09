#!/usr/bin/env python

import threading
from threading import Thread, Lock, Event, Semaphore
import collections
import os
import sys
from collections import OrderedDict
from decimal import *
from enum import Enum
import ndnlog
import re
from pyndn import Name

getcontext().prec = 6
# tracePatternString="(?P<timestamp>[0-9]+\.[0-9]+)\sDEBUG:\s\[Forwarder\]\son(?P<direction>Outgoing|Incoming)(Data|Interest)\sface=(?P<face>[0-9]+)\s(?P<traceType>data|interest)=(/[A-z0-9_\-\+]+)+/(?P<frame_type>d|k)/(?P<frame_no>[0-9]+)/(?P<data_type>data|parity)/(?P<seg_no>[%0-9a-fA-F]+)(/[0-9]+/(?P<play_no>[0-9]+)/(?P<segnum>[0-9]+)/(?P<psegnum>[0-9]+))?"
#tracePatternString="(?P<timestamp>[0-9]+\.[0-9]+)\sDEBUG:\s\[Forwarder\]\son(?P<direction>Outgoing|Incoming)(Data|Interest)\sface=(?P<face>[0-9]+)\s(?P<traceType>data|interest)=(/[%A-z0-9_\-\+\.]+)+/ndnrtc/%FD%[0-9a-fA-F]+/(?P<stream_type>video|audio)/(?P<stream>\w+)/(?P<thread>\w+)/(?P<frame_type>d|k)/(?P<frame_no>%FE[\w%\+-]+)(/(?P<parity>_parity))?/(?P<seg_no>[%0-9a-fA-F]+)"
tracePatternString="(?P<timestamp>[0-9]+\.[0-9]+)\sDEBUG:\s\[Forwarder\]\son(?P<direction>Outgoing|Incoming)(Data|Interest)\sface=(?P<face>[0-9]+)\s(?P<traceType>data|interest)=(/[%A-z0-9_\-\+\.]+)+/ndnrtc/%FD%[0-9a-fA-F]+/(?P<stream_type>video|audio)/(?P<stream>\w+)/(?P<thread>\w+)/(?P<frame_type>d|k)/(?P<frame_no>%FE[\w%\+-]+)/(?P<seg_no>[%0-9a-fA-F]+)"

if len(sys.argv) < 2:
  print "usage: "+__file__+" <nfd1.log> [<nfd2.log> ...]"
  print ""
  print "\tThis script is used for tracing actual interests and data objects through several NFD instances"
  print "\tDepending on the number of NFD log files supplied, script will print out timestamps of moments"
  print "\twhen certain NDN-RTC interest/data object has entered NFD and left it. Thus, for each hub provided"
  print "\tthere will be 4 columns with timestamps: interest in, interest out, data in, data out."
  print "\tIf more than one log file is provided, script will trace same interest/data accross all log files."
  print "\tIn general form, if N NFD log files are provided, each output row will look like this:"
  print ""
  print "\tSeg Key\t\t|<-HUB1->|\t|<-HUB2->| ...\t|<-HUBN->|\t|<-HUBN->| ...\t|<-HUB2->|\t|<-HUB1->|"
  print "\t----------------------------------------------------------------------------------------------------------"
  print "\tFrameNo-SegNo\ti_in i_out\ti_in i_out ...\ti_in i_out\td_in d_out ...\td_in d_out\td_in d_out"
  print ""
  exit(1)

def getThreadName():
    return threading.current_thread().name

def sequenceNoToInt(seqNoComp):
	n = Name(seqNoComp)
	return int(n[0].toSequenceNumber())

def segNoToInt(segNo):
  return int(''.join(segNo.split("%")[1:]), 16)

class TraceType(Enum):
	data = 1
	interest = 2

	@staticmethod
	def FromString(traceTypeStr):
		try:
			return {'data':TraceType.data, 'interest':TraceType.interest}[str.lower(traceTypeStr)]
		except:
			return None

	def __str__(self):
		return {TraceType.data:'data', TraceType.interest:'interest'}[self]

class HubTraceEntry:
	""" Hub trace represents interest or data being forwarded through the hub
	Trace has two main attributes:
		- inTimestamp - a timestamp, when interest/data has entered forwarder
		- outTimestamp - a timestamp when interest/data has left forwarder
	"""
	def __init__(self, *args, **kwargs):
		self.lock = Lock()
		self.frameNo = kwargs.get('frameNo', None)
		self.segNo = kwargs.get('segNo', None)
		self.inTimestamp = kwargs.get('inTimestamp', None)
		self.outTimestamp = kwargs.get('outTimestamp', None)
		self.type = kwargs.get('traceType', None)

	def isComplete(self):
		return (self.inTimestamp != None and self.outTimestamp != None and self.type != None)

	def isIn(self):
		return self.inTimestamp != None

	def isOut(self):
		return self.outTimestamp != None

	# trace is distinguished by combination of inTimestamp and frame&segment pair
	# this way it can be sorted chronologically
	def getKey(self):
		if (self.inTimestamp != None or self.outTimestamp != None) and self.getFrameKey() != None:
			if self.inTimestamp != None:
				return str(self.inTimestamp)+':'+self.getFrameKey()
			else:
				return str(self.outTimestamp)+':'+self.getFrameKey()
		return None

	def getFrameKey(self):
		if self.frameNo != None and self.segNo != None:
			return str(self.frameNo)+'-'+str(self.segNo)
		return None

	def getProcessingTime(self):
		if self.outTimestamp and self.inTimestamp:
			return self.outTimestamp - self.inTimestamp
		return None

	def setInTimestamp(self, timestamp):
		self.lock.acquire()
		self.inTimestamp = Decimal(timestamp)
		self.lock.release()

	def setOutTimestamp(self, timestamp):
		self.lock.acquire()
		self.outTimestamp = Decimal(timestamp)
		self.lock.release()

	def setType(self, traceType):
		self.lock.acquire()
		self.type = traceType
		self.lock.release()

	def getArrayRepr(self):
		arrayRepr = []
		arrayRepr.append(self.inTimestamp) 
		arrayRepr.append(self.outTimestamp)
		return arrayRepr

	def __eq__(self, other):
		if other == None:
			return False
		if isinstance(other, HubTraceEntry):
			return (self.isComplete() and other.isComplete()) and (self.type == other.type) and (self.getKey() == other.getKey())
		if isinstance(other, str):
			return (self.getFrameKey() != None and self.getFrameKey() == other)
		return False

	def __str__(self):
		return str(self.inTimestamp)+'\t'+str(self.outTimestamp)

	def __repr__(self):
		return self.__str__()

class SegmentTraceEntry:
	""" Segment trace entry connects interest and data traces into 
	one chain, therefore giving a copmlete trace of requesting frame
	segment accross multiple hubs.
	Segment trace always starts with interests and may end with data
	(if segment interest was answered)
	"""
	def __init__(self, nHubs, frameNo, segNo):
		self.frameNo = frameNo
		self.segNo = segNo
		self.lock = Lock()
		self.nHubs = nHubs
		self.upstreamTraces = [None for i in range(0, self.nHubs)]
		self.downstreamTraces = [None for i in range(0, self.nHubs)]
		self.complete = False
		
	def addTrace(self, isUpstream, hubNo, trace):
		if trace.getFrameKey() == self.getKey():
			if hubNo < self.nHubs:
				self.lock.acquire()
				if isUpstream:
					self.upstreamTraces[hubNo] = trace
				else:
					self.downstreamTraces[hubNo] = trace
				self.lock.release()
		else:
			raise Exception('unexpected trace added', trace.getFrameKey(), self.getKey())

	def getTrace(self, hubNo, isUpstream):
		if isUpstream:
			return self.upstreamTraces[hubNo]
		else:
			return self.downstreamTraces[hubNo]

	def isValid(self):
		if not self.upstreamTraces[0] or not self.upstreamTraces[0].inTimestamp:
			return False
		return True

	def startTimestamp(self):
		if not self.upstreamTraces[0].inTimestamp:
			if not self.upstreamTraces[0].outTimestamp:
				raise Exception('no IN, no OUT timestamps', self)
			else:
				return self.upstreamTraces[0].outTimestamp
		return self.upstreamTraces[0].inTimestamp

	def getKey(self):
		return str(self.frameNo)+'-'+str(self.segNo)

	def getSortKey(self):
		return str(self.startTimestamp())+'-'+self.getKey()

	def getArrayRepr(self):
		arrayRepr = [self.getKey()]
		downstreamReverse = list(self.downstreamTraces)
		downstreamReverse.reverse()		
		for hubTrace in self.upstreamTraces + downstreamReverse:
			if hubTrace:
				arrayRepr.extend(hubTrace.getArrayRepr())
			else:
				arrayRepr.extend([None, None])
		return arrayRepr

	def getProcessingTimesString(self):
		s = self.getKey()+'\t'
		lastTimestamp = None
		downstreamReverse = list(self.downstreamTraces)
		downstreamReverse.reverse()
		first = True
		for hubTrace in self.upstreamTraces + downstreamReverse:
			ss = None
			if hubTrace:
				if lastTimestamp and hubTrace.inTimestamp:
					proc = hubTrace.inTimestamp - lastTimestamp
					s += str(proc)+'\t'
				elif not first:
					s += '.\t'
				if hubTrace.getProcessingTime():
					s += str(hubTrace.getProcessingTime())+'\t'
				else:
					s += '.\t'
				lastTimestamp = hubTrace.outTimestamp
				first = False
		return s

	def __str__(self):
		self.lock.acquire()
		s = self.getKey()+'\t'
		downstreamReverse = list(self.downstreamTraces)
		downstreamReverse.reverse()
		for hubTrace in self.upstreamTraces + downstreamReverse:
			if hubTrace:
				s += str(hubTrace) + '\t'
			else:
				s += '.' + '\t'
		self.lock.release()
		return s

	def __repr__(self):
		return self.__str__()

def onTraceDetected(timestamp, match, userData):
	global traces
	global traceLock
	global nHubs
	global hubTraces
	global operatingTracesDictList

	hubNo = userData['userData']
	frameNo = sequenceNoToInt(match.group('frame_no'))
	segNo = segNoToInt(match.group('seg_no'))
	traceType = TraceType.FromString(match.group('traceType'))
	traceKey = str(frameNo)+'-'+match.group('frame_type')+'-'+str(segNo)+'-'+str(traceType)
	isIn = (match.group('direction') == 'Incoming')
	isOut = not isIn

	traceLock.acquire()
	hubTracesList = hubTraces[hubNo]
	operatingTracesDict = operatingTracesDictList[hubNo]
	
	tempTraceEntry = HubTraceEntry(frameNo=frameNo, segNo=segNo, traceType=traceType)
	if isIn:
		tempTraceEntry.setInTimestamp(timestamp)
	if isOut:
		tempTraceEntry.setOutTimestamp(timestamp)

	if not operatingTracesDict.has_key(traceKey):
		if isIn: # we expect this to be 'in' trace
			operatingTracesDict[traceKey] = tempTraceEntry
		else: # seems, like we're answering cached data...
			hubTracesList.append(tempTraceEntry)
			# raise Exception('unexpected emission', hubNo, timestamp, traceKey)
	else: 
		traceEntry = operatingTracesDict[traceKey]
		if isOut: # we expect this to be 'out' trace
			# stored trace should be 'in' only - as we got 'out' trace
			if traceEntry.inTimestamp and not traceEntry.outTimestamp:
				traceEntry.setOutTimestamp(timestamp)
				# make sure trace is complete now
				if traceEntry.isComplete():
					# now we can flush this trace to hubTracesList
					hubTracesList.append(traceEntry)
					# and remove it from operatingTracesDict
					del operatingTracesDict[traceKey]
				else:
					raise Exception('complete trace expected', hubNo, str(traceEntry))
			else:
				raise Exception('"in" trace expected', hubNo, str(traceEntry))
		else:
			print "Warning: out trace expected "+str(hubNo)+str(timestamp)+str(traceKey)+str(tempTraceEntry)+str(traceEntry)
			#raise Exception('"out" trace expected', hubNo, timestamp, traceKey, str(tempTraceEntry), str(traceEntry))
	traceLock.release()
	return True

class ParseThread(Thread):
	def __init__(self, logFile, actions):
		Thread.__init__(self)
		self.logFile = logFile
		self.actions = actions

	def run(self):
		ndnlog.parseLog(self.logFile, self.actions)

# ****
logFiles = sys.argv[1:len(sys.argv)]
nHubs = len(logFiles)
traceLock = Lock()
segmentTraces = []

# hubTraces is a list of traces lists, each element of which contains
# HubTraceEntry instance
# hubTraces is a shared IPC object which is being filled by several 
# worker threads simultaneously
# each thread fills up it's own trace list
hubTraces = [[] for i in range(0,nHubs)]

# operatingTracesDictList is a list of traces dictionaries, each key 
# of which is a frame key (see HubTraceEntry definition of getFrameKey
# method) and value is an instance of HubTraceEntry
# during parsing, each working thread may encounter either incoming or
# outgoing data/interest
# in order to obtain full trace information - thread needs to collect 
# both incoming and outgoing parts
# operating dictionaries contain these parts during log parsing
# once both parts are collected from the log, this hub trace entry is
# removed and added to the approriate hubTraces's list
operatingTracesDictList = [{} for i in range(0,nHubs)]

logActions = []
for i in range(0,nHubs):
	actions = {}
	actions['pattern'] = re.compile(tracePatternString)
	actions['tfunc'] = lambda match: Decimal(match.group('timestamp'))
	actions['func'] = onTraceDetected
	actions['userData'] = i
	logActions.append(actions)

workers = []
for i in range(0,nHubs):
	logActions[i]['userdata'] = i
	thread = ParseThread(logFiles[i], [logActions[i]])
	workers.append(thread)
	print 'starting parser on '+logFiles[i]+'...'
	thread.start()

for i in range(0,nHubs):
	workers[i].join()

print 'parsing done.'
for i in range(0,nHubs):
	# flush incomplete traces into traces lists
	hubTraces[i].extend(operatingTracesDictList[i].values())
	sortedTraces = sorted(hubTraces[i], key=lambda trace: trace.getKey())
	hubTraces[i] = sortedTraces
	print 'hub traces number in '+logFiles[i]+' is '+str(len(hubTraces[i]))
	# print 'incomplete hub traces number in '+logFiles[i]+' is '+str(len(operatingTracesDictList[i].keys()))
	#print operatingTracesDictList[i]

print 'connecting traces accross multiple hubs...'

#***
def getLatestTrace(traceList, traceType):
	found = False
	i = len(traceList)-1
	trace = None
	while not found and i >= 0:
		trace = traceList[i]
		found = (trace.type == traceType)
		i -= 1
	if found:
		del traceList[i+1]
	else:
		trace = None
	return trace

def getLatestTraceByKey(traceList, traceType, frameKey):
	found = False
	i = len(traceList)-1
	trace = None
	while not found and i >= 0:
		trace = traceList[i]
		found = (trace.type == traceType and trace.getFrameKey() == frameKey)
		i -= 1
	if found:
		del traceList[i+1]
	else:
		trace = None
	return trace

def areTraceListsEmpty():
	global hubTraces
	for traceList in hubTraces:
		if len(traceList) != 0:
			return False
	return True

def printHubTracesLenghts():
	global hubTraces
	s = 'traces lists: '
	for i in range(0,len(hubTraces)):
		s += str(i)+': '+str(len(hubTraces[i]))+'\t'
	print s

complete = False
currentHub = 0
traceType = TraceType.interest
assemblingTrace = None
traces = []
nIterations = 0
debug = False
while not complete:
	debug = (assemblingTrace.getKey() == '2657-0') if assemblingTrace else None
	hubTrace = None
	if assemblingTrace:
		hubTrace = getLatestTraceByKey(hubTraces[currentHub], traceType, assemblingTrace.getKey())
		if not hubTrace:
			if debug:
				print 'hub '+str(currentHub)+' doesn\'t have traces for '+assemblingTrace.getKey()+'. saving trace '+str(assemblingTrace)
			traces.append(assemblingTrace)
			assemblingTrace = None
			currentHub = 0
			traceType = TraceType.interest
		else:
			if debug:
				print 'new trace in hub '+str(currentHub)+': '+str(hubTrace)
	
	if not assemblingTrace:
		hubTrace = getLatestTrace(hubTraces[currentHub], traceType)
		debug = (hubTrace.getFrameKey() == '2657-0') if hubTrace else None
		if debug:
			print hubTrace.getFrameKey() + ' start in '+str(currentHub)+': '+str(hubTrace)
		if not hubTrace:
			if currentHub == nHubs-1:
				complete = True
			else:
				currentHub += 1
		else:
			# print 'got latest hubtrace '+str(hubTrace)
			assemblingTrace = SegmentTraceEntry(nHubs, hubTrace.frameNo, hubTrace.segNo)
			# print 'starting new segment trace '+assemblingTrace.getKey()

	if hubTrace:
		assemblingTrace.addTrace(hubTrace.type == TraceType.interest, currentHub, hubTrace)
		# if debug:
		# 	print 'added '+hubTrace.getFrameKey()+' to segment trace: '+str(assemblingTrace)
		# check, if this trace is 'out' and continue search
		# in following hubs
		if hubTrace.isOut():
			if traceType == TraceType.interest:
				if currentHub == nHubs-1:
					traceType = TraceType.data
				else:
					currentHub += 1
			else:
				if currentHub == 0:
					traces.append(assemblingTrace)
					# print 'new trace '+str(assemblingTrace)
					assemblingTrace = None
					traceType = TraceType.interest
				else:
					currentHub -= 1
		else: 
			# trace is not 'out' - most probably it was answered by cached data if 
			# there was an interest
			if hubTrace.isIn():
				if hubTrace.type == TraceType.interest:
					# look for answerred cached data in next iteration
					traceType = TraceType.data
					# print 'IN interest'
				else:
					# it seems that it was a data that entered the hub
					# but never left it for some reason. save assemblingTrace 
					# if any and flush
					if assemblingTrace:
						# print 'new incomplete trace '+str(assemblingTrace)
						traces.append(assemblingTrace)
						assemblingTrace = None
					currentHub = 0
					traceType = TraceType.interest
			else:
				raise Exception('unexpected hub trace', hubTrace)
		complete = areTraceListsEmpty()
		nIterations += 1
		if (nIterations%10000 == 0) or (complete == True):
			print str(nIterations)+' iterations completed. '+str(len(traces))+' traces revealed'
			printHubTracesLenghts()

print 'checking traces validity...'
nInvalid = 0
n = len(traces)
while i < n:
	segmentTrace = traces[i]
	if not segmentTrace.isValid():
		nInvalid += 1
		print 'invalid trace '+str(segmentTrace)
		del traces[i]
		n -= 1
	else:
		i += 1

print str(nInvalid)+' invalid traces deleted'
print 'arranging traces chronologically....'
sortedTraces = sorted(traces, key=lambda segmentTrace: segmentTrace.getSortKey())

print 'creating timestamps table...'
timestampsTable = [sortedTraces[i].getArrayRepr() for i in range(0,len(sortedTraces))]

outFile = 'traces.log'
print 'writing traces into '+outFile

def subtractTimestamps(tsArray1, tsArray2):
	if len(tsArray1) == len(tsArray2):
		sub = [None for i in range(0, len(tsArray1))]
		for i in range(1, len(tsArray1)):
			if tsArray1[i] and tsArray2[i]:
				sub[i] = tsArray1[i] - tsArray2[i]
		return sub
	else:
		raise Exception('unequal timestamp arrays lengths', tsArray1, tsArray2)

def renderTimestamps(tsArray, sub):
	if sub and len(tsArray) != len(sub):
		raise Exception('unequal arrays lengths', tsArray, sub)
	s = ''
	i = 0
	rtt = None
	if tsArray[-1]:
		rtt = tsArray[-1]-tsArray[1]
	mid = (len(tsArray)-1)/2 # 1st element is a key number
	genDelay = None
	if tsArray[mid+1] and tsArray[mid]:
		genDelay = int((tsArray[mid+1] - tsArray[mid])*1000)
	for el in tsArray:
		s += str(el) if el else '-'
		if sub and sub[i]:
			s += ' ^'+str(int(sub[i]*1000))+'ms'
		i += 1
		if i == mid+1:
			if genDelay:
				s += '\t|<-'+str(genDelay)+'ms->|'
			else:
				s += '\t|<-???->|'
		s += '\t'
	if rtt:
		s += 'rtt ' + str(int(rtt*1000)) + 'ms'
	return s

prevTimestamps = [None for i in range(0, len(timestampsTable[0]))]
with open(outFile, "w") as file:
	for line in timestampsTable:
		sub = None
		sub = subtractTimestamps(line, prevTimestamps)
		s = renderTimestamps(line, sub)
		print>>file, s
		prevTimestamps = [line[i] if line[i] else prevTimestamps[i] for i in range(0,len(line))]

print 'done.'
