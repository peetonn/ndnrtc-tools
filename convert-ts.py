#!/usr/bin/env python

import ndnlog
import sys
import time
from ndnlog import NdnLogToken

startTimestamp = None
baseTimestamp = None

def onLogEntry(timestamp, match, userData):
	global startTimestamp
	global baseTimestamp
	
	if not startTimestamp:
		startTimestamp = int(timestamp)
	if not baseTimestamp:
		baseTimestamp = int(time.time()*1000)
	
	newTimestamp = baseTimestamp + (timestamp - startTimestamp)
	print str(newTimestamp) + "\t[" + match.group('log_level') + "][" + match.group('component_name') + "]-" + match.group('component_address') + ': ' + match.group('message')

	return True

if __name__ == '__main__':
	if len(sys.argv) < 2:
		print "usage: "+__file__+" <log_file>"
		exit(1)
	logFile = sys.argv[1]

	parseActions = {}
	parseActions['pattern'] = ndnlog.compileNdnLogPattern('.*', '.*', '.*')
	parseActions['tfunc'] = ndnlog.DefaultTimeFunc
	parseActions['func'] = onLogEntry
	
	ndnlog.parseLog(logFile, [parseActions])