#!/usr/bin/env python

import ndnlog
import getopt
import sys
from ndnlog import NdnLogToken
from collections import OrderedDict

verbose = False

def log(msg):
	global verbose
	if verbose:
		sys.stderr.write(msg+"\n")

def error(msg):
	global verbose
	if verbose:
		sys.stderr.write("error: "+msg+"\n")

def fatal(msg):
	global verbose
	if verbose:
		sys.stderr.write(msg+"\n")
	exit(1)

#******************************************************************************
def usage():
	print "usage: "+sys.argv[0]+" -f<log_file>"
	sys.exit(0)

scheduledDelay = 0
actualScheduledTime = 0
actualFireTime = 0

lastTimestamp = 0
lastInterruptionTs = 0
lastInterruptionDelay = 0

def timeFunc(match):
	global lastTimestamp, lastInterruptionTs, lastInterruptionDelay
	ts = int(match.group('timestamp'))
	if lastTimestamp != 0:
		delay = ts - lastTimestamp
		if delay > 50:
			lastInterruptionTs = ts
			lastInterruptionDelay = delay
			# print "delay "+str(delay)+" at "+str(ts) + " "+str(ts)+" "+str(lastTimestamp)
	lastTimestamp = ts
	return ts

def nullFunc(timestamp, match, userInfo):
	return True

def onTimerScheduled(timestamp, match, userInfo):
	global actualScheduledTime, scheduledDelay
	scheduledDelay = int(match.group('delay'))
	actualScheduledTime = int(timestamp)
	return True

def onTimerFired(timestamp, match, userInfo):
	global actualScheduledTime, scheduledDelay, actualFireTime, lastInterruptionTs, lastInterruptionDelay
	actualFireTime = int(timestamp)
	actualDelayTime = actualFireTime - actualScheduledTime
	if actualDelayTime != 0:
		ratio = abs(float(actualDelayTime - scheduledDelay)) / float(actualDelayTime)
		if ratio > 0.5:
			print str(timestamp)+" actual delay "+str(actualDelayTime) + " bigger than scheduled "+str(scheduledDelay) + \
			" (" + str(ratio) + ") last interrupt "+str(lastInterruptionDelay)+"ms at "+str(lastInterruptionTs) + " (" + \
			str(timestamp-lastInterruptionTs)+"ms ago)"
			lastInterruptionTs = 0
			lastInterruptionDelay = 0

	return True

def run(logFile):
	global interests
	
	interruptActions = {}
	interruptActions['pattern'] = ndnlog.compileNdnLogPattern('.*', '.*', '.*')
	interruptActions['tfunc'] = timeFunc
	interruptActions['func'] = nullFunc

	timerScheduledRegexString = "timer wait\s(?P<delay>[0-9]+)"
	timerScheduledActions = {}
	timerScheduledActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', timerScheduledRegexString)
	timerScheduledActions['tfunc'] = ndnlog.DefaultTimeFunc
	timerScheduledActions['func'] = onTimerScheduled

    #enqueue interest
	timerFireRegexString = "\[ proc start"
	timerFiredActions = {}
	timerFiredActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', timerFireRegexString)
	timerFiredActions['tfunc'] = ndnlog.DefaultTimeFunc
	timerFiredActions['func'] = onTimerFired

	ndnlog.parseLog(logFile, [interruptActions, timerScheduledActions, timerFiredActions])

def main():
	global verbose
	logFile = None
	try:
		opts, args = getopt.getopt(sys.argv[1:], "f:t:", ["log-file=", "threshold="])
	except getopt.GetoptError as err:
		print str(err)
		usage()
		sys.exit(2)
	for o, a in opts:
		if o in ("-f", "--log-file"):
			logFile = a
			print "log file is "+logFile
		elif o in ("-t", "--threshold"):
			threshold = float(a)
		elif o in ("-v"):
			verbose = True
		else:
			assert False, "unhandled option "+o
	if not logFile:
		usage();
		exit(1)
	run(logFile)
	

if __name__ == '__main__':
	main()