#!/usr/bin/env python

import sys
from pyndn import Name

if len(sys.argv) < 2:
  print "usage: "+__file__+" [<log_file> | - ]"
  print "This script converts canonical NDN sequence numbers into human-readable number"
  exit(1)

if __name__ == '__main__':
	logFile = sys.argv[1]
	lastBufferAppend = {}

	def processLine(line):
		comps = [comp for comp in line.split("/") if comp.startswith('%FE')]
		if len(comps):
			for c in comps:
				num = Name(c)[-1].toSequenceNumber()
				line = line.replace(c, str(num))
		sys.stdout.write(line)

	if logFile == '-':
		for line in sys.stdin:
			processLine(line)
	else:
		with open(logFile) as f:
			for line in f:
				processLine(line)  
