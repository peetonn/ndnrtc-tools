#!/usr/bin/env python

import sys
import getopt
import re

# extracts a chunk of log file around given frame number;
# IMPORTANT: pass log file through toseqno.py first!

lastTimestamp = None
def getFrameNo(line, isKey):
	regexStr = ".*k/(?P<frameno>[0-9]+)/%00%00" if isKey else ".*d/(?P<frameno>[0-9]+)/%00%00"
	regex = re.compile(regexStr)
	m  = regex.match(line)
	if m:
		return int(m.group('frameno'))
	return None

if __name__ == '__main__':
	try:
		opts, args = getopt.getopt(sys.argv[1:], "i:rlk", ["interval="])
	except getopt.GetoptError as err:
		print str(err)
		sys.exit(2)

	frameRange=0
	leftPart = True
	rightPart = True
	isKey = False

	for o, a in opts:
		if o in ("-i", "--interval"):
			frameRange = int(a)
		elif o in ("-r"):
			leftPart = False
		elif o in ("-l"):
			rightPart = False
		elif o in ("-k"):
			isKey = True
		else:
			assert False, "unhandled option "+o

	if len(args) < 1:
		print "provide timestamp"
		exit(2)
	
	baseFrame = int(args[0])

	# print "extracting chunk of [-"+str(frameRange)+";"+str(frameRange)+"] around "+str(baseFrame)

	withinRange = False
	for line in sys.stdin:
		fno = getFrameNo(line, isKey)

		printLine = False
		if fno != None:
			withinRange = (fno >= baseFrame-frameRange and fno <= baseFrame+frameRange)
			if not (leftPart and rightPart):
				if leftPart:
					withinRange = (fno >= baseFrame-frameRange and fno <= baseFrame)
				if rightPart:
					withinRange = (fno >= baseFrame and fno <= baseFrame+frameRange)
	
		if not withinRange:
			continue
		sys.stdout.write(line)

