#!/usr/bin/env python

import sys
import getopt
import re

firstTimestamp = None

def normalizeTimestamp(line):
	global firstTimestamp
	try:
		ts = 0
		comps = re.split("[\t ]+", line)
		if len(comps) > 0:
			ts = float(comps[0])
			# check number of digits - if it's 10 then timestamp is in seconds
			# and adjustment is needed
			if len(str(int(ts))) == 10:
				ts = ts*1000
			if not firstTimestamp:
				firstTimestamp = ts
			ts -= firstTimestamp
			if ts >= 0:
				line = line.replace(comps[0], str(ts), 1)
	except:
		return line
	return line

if __name__ == '__main__':
	try:
		opts, args = getopt.getopt(sys.argv[1:], "t:", ["-threshold"])
	except getopt.GetoptError as err:
		print str(err)
		sys.exit(2)
	threshold=7
	for o, a in opts:
		if o in ("-t", "--threshold"):
			threshold = float(a)
		else:
			assert False, "unhandled option "+o
	for line in sys.stdin:
		line = normalizeTimestamp(line)
		sys.stdout.write(line)

