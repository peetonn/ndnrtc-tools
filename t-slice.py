#!/usr/bin/env python

import sys
import getopt
import re

def getTimestamp(line):
	try:
		ts = 0
		comps = re.split("[\t ]+", line)
		if len(comps) > 0:
			ts = float(comps[0])
			# check number of digits - if it's 10 then timestamp is in seconds
			# and adjustment is needed
			if len(str(int(ts))) == 10:
				ts = ts*1000
	except:
		return None
	return ts

if __name__ == '__main__':
	try:
		opts, args = getopt.getopt(sys.argv[1:], "", ["start=", "end="])
	except getopt.GetoptError as err:
		print str(err)
		sys.exit(2)
	startTs=None
	endTs=None
	for o, a in opts:
		if o in ("--start"):
			startTs = float(a)
		elif o in ("--end"):
			endTs = float(a)
		else:
			assert False, "unhandled option "+o
	if not startTs or not endTs:
		print "please provide start and end timestamps"
		exit(2)

	for line in sys.stdin:
		ts = getTimestamp(line)
		if ts >= startTs and ts <= endTs:
			sys.stdout.write(line)
