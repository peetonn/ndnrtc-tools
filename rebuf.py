#!/usr/bin/env python

import ndnlog
import sys
from ndnlog import NdnLogToken

if len(sys.argv) < 2:
  print "usage: "+__file__+" <log_file>"
  exit(1)

def onBufferAppendDetected(timestamp, match, userData):
	global lastBufferAppend
	lastBufferAppend['frame_no'] = match.group('frame_no')
	lastBufferAppend['seg_no'] = match.group('seg_no')
	return True

def onRebufferingDetected(timestamp, match, userData):
	global lastBufferAppend
	print 'rebuffering #'+match.group('rebuf_no')+' detected at '+str(timestamp)
	print 'w: '+match.group('cur_w')+' default w: '+match.group('default_w')
	print 'last appended: '+lastBufferAppend['frame_no']+'-'+lastBufferAppend['seg_no'] +'\t'+ lastBufferAppend['frame_no']+'/data/'+ndnlog.intToSegNo(int(lastBufferAppend['seg_no']))
	print ''
	return True

if __name__ == '__main__':
	logFile = sys.argv[1]
	lastBufferAppend = {}

	bufferAppendRegexString = 'append: \[(?P<frame_no>[0-9]+)-(?P<seg_no>[0-9]+)\]'
	appendActions = {}
	appendActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.debug.__str__(), '.consumer-buffer', bufferAppendRegexString)
	appendActions['tfunc'] = lambda match: int(match.group('timestamp'))
	appendActions['func'] = onBufferAppendDetected

	# deprecated 
	# rebufferingRegexString = 'No data for the last (?P<interrupt>[0-9]+) ms. Rebuffering (?P<rebuf_no>[0-9]+) curent w (?P<cur_w>[0-9]+) default w (?P<default_w>[0-9]+)'
	rebufferingRegexString = 'rebuffering #(?P<rebuf_no>[0-9]+) seed (?P<seed>[0-9]+) key (?P<key>[0-9]+) delta (?P<delta>[0-9]+) curent w (?P<cur_w>[0-9]+) default w (?P<default_w>[0-9]+)'
	rebufferingActions = {}
	rebufferingActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.warning.__str__(), '.consumer-pipeliner', rebufferingRegexString)
	rebufferingActions['tfunc'] = lambda match: int(match.group('timestamp'))
	rebufferingActions['func'] = onRebufferingDetected

	ndnlog.parseLog(logFile, [appendActions, rebufferingActions])
