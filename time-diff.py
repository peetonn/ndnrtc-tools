#!/usr/bin/env python

import sys

def getTimestamp(line):
	try:
		ts = float(line.split("\t")[0])
	except:
		return None
	return ts

threshold=7
prevLine = None
for line in sys.stdin:
	if prevLine:
		sys.stdout.write(prevLine)

		tsPrevMs = getTimestamp(prevLine)
		tsCurMs = getTimestamp(line)
		if tsPrevMs and tsCurMs:
			diffMs = (tsCurMs - tsPrevMs)
			if diffMs > threshold:
				diffSec = diffMs/1000
				sys.stdout.write("\t^ {0}sec {1}ms\n".format(diffSec, diffMs))
	else:
		sys.stdout.write(line)
	prevLine = line
