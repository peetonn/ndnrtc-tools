#!/usr/bin/env python

import sys
import getopt
import re

# extracts frame numbers according to regex (interest or data) and prints them out
# user may optionally provide trigger event regex. in this case, last frame number
# will be printed out only when trigger regex matches.
# for example, one may find last frame numbers before starvation event like this:
# countframe.py --trigger="Starvation"

# IMPORTANT: pass log file through toseqno.py first!

def getFrameNo(line, isKey):
	regexStr = ".*k/(?P<frameno>[0-9]+)/%00%00" if isKey else ".*d/(?P<frameno>[0-9]+)/%00%00"
	regex = re.compile(regexStr)
	m  = regex.match(line)
	if m:
		return int(m.group('frameno'))
	return None

if __name__ == '__main__':
	try:
		opts, args = getopt.getopt(sys.argv[1:], "t:k", ["trigger="])
	except getopt.GetoptError as err:
		print str(err)
		sys.exit(2)

	frameRange=0
	triggerRegex=None
	isKey = False

	for o, a in opts:
		if o in ("-t", "--trigger"):
			triggerRegex = re.compile(".*"+a+".*")
		elif o in ("-k"):
			isKey = True
		else:
			assert False, "unhandled option "+o

	withinRange = False
	lastFrameNo = 0
	for line in sys.stdin:
		fno = getFrameNo(line, isKey)
		if triggerRegex:
			m = triggerRegex.match(line)
			if m:
				sys.stdout.write(str(lastFrameNo)+'\n')
		else:
			if fno:
				sys.stdout.write(str(fno)+'\n')
		if fno:
			lastFrameNo = fno

