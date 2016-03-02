#!/usr/bin/env python

import sys
import getopt

def getTimestamp(line):
	try:
		ts = float(line.split("\t")[0])
	except:
		return None
	return ts

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
	prevLine = None
	for line in sys.stdin:
		if prevLine:
			#sys.stdout.write(prevLine)
			tsPrevMs = getTimestamp(prevLine)
			tsCurMs = getTimestamp(line)
			if tsPrevMs and tsCurMs:
				diffMs = (tsCurMs - tsPrevMs)
				if diffMs > threshold:
					diffSec = diffMs/1000
					print tsPrevMs
					sys.stdout.write("\t^ {0}sec {1}ms\n".format(diffSec, diffMs))
		#else:
			#sys.stdout.write(line)
		prevLine = line
