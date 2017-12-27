#!/usr/bin/env python

import sys
import re
from pyndn import Name

if len(sys.argv) < 2:
  print "usage: "+__file__+" [<log_file> | - ]"
  print "This script converts canonical NDN sequence numbers into human-readable number"
  exit(1)

if __name__ == '__main__':
	logFile = sys.argv[1]
	lastBufferAppend = {}
	p = re.compile('(%FE[\w%\+\-\.]+)')

	def processLine(line):
		# comps = [comp for comp in line.split("/") if comp.startswith('%FE')]
		comps = re.findall(p, line)
		# print line
		if len(comps):
			# print comps
			for c in comps:
				seq = c
				# print(seq)
				num = Name(seq)[-1].toSequenceNumber()
				line = line.replace(seq, str(num))
		sys.stdout.write(line)

	if logFile == '-':
		for line in sys.stdin:
			processLine(line)
	else:
		with open(logFile) as f:
			for line in f:
				processLine(line)  
