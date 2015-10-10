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

interests = OrderedDict()
count=0
threshold=100
# key - "frameNo-segNo"
# value - {'enq':enqueueTimestamp, 'exp':expressTimestamp}

def onInterestsExpressed(timestamp, match, userInfo):
	global interests
	global count, threshold
	keyNo = match.group('frame_no')
	segNo = ndnlog.segNoToInt(match.group('seg_no'))
	t = 'd' if match.group('data_type') == 'data' else 'p' 
	segKey = str(keyNo)+ '-' + str(segNo)+t
	if not segKey in interests.keys():
		interests[segKey] = {}
	interests[segKey]['exp'] = timestamp
	interests[segKey]['expQsize'] = match.group('qsize')
	diff=interests[segKey]['exp']-interests[segKey]['enq']
	
	
	if diff>=threshold:
		count=count+1
		print segKey, interests[segKey], 'Difference:', diff,'!!!!diff>='+str(threshold)
	else:
		print segKey, interests[segKey], 'Difference:', diff
	return True

def onInterestsEnqueue(timestamp, match, userInfo):
	global interests

	keyNo = match.group('frame_no')
	segNo = ndnlog.segNoToInt(match.group('seg_no'))
	print str(timestamp)+" segNo "+match.group('seg_no')
	t = 'd' if match.group('data_type') == 'data' else 'p' 
	segKey = str(keyNo)+ '-' + str(segNo)+t
	if not segKey in interests.keys():
		interests[segKey] = {}
	interests[segKey]['enq'] = timestamp
	interests[segKey]['enqQsize'] = match.group('qsize')
	return True

def run(logFile):
	global interests
	
	#express interest
	expressRegexString = "express\s"+ndnlog.NdnRtcNameRegexString+"\s.*lifetime:\s(?P<lifetime>[0-9]+)\sqsize:\s(?P<qsize>[0-9]+)"
	iqueueExpressActions = {}
	iqueueExpressActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.stat.__str__(), 'iqueue', expressRegexString)
	iqueueExpressActions['tfunc'] = ndnlog.DefaultTimeFunc
	iqueueExpressActions['func'] = onInterestsExpressed

    #enqueue interest
	enqueueRegexString = "enqueue\s"+ndnlog.NdnRtcNameRegexString+"\s.*lifetime:\s(?P<lifetime>[0-9]+)\sqsize:\s(?P<qsize>[0-9]+)"
	iqueueEnqueueActions = {}
	iqueueEnqueueActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.debug.__str__(), 'iqueue', enqueueRegexString)
	iqueueEnqueueActions['tfunc'] = ndnlog.DefaultTimeFunc
	iqueueEnqueueActions['func'] = onInterestsEnqueue

	ndnlog.parseLog(logFile, [iqueueEnqueueActions, iqueueExpressActions])


	#print interests,'\n'
	#for key in interests:
	#	print key, interests[key], 'Difference:', interests[key]['exp']-interests[key]['enq']

def main():
	global verbose
	global count, threshold

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
	print 'count >='+str(threshold),count
	

if __name__ == '__main__':
	main()