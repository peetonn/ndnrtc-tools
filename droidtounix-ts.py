#!/usr/bin/env python

import sys
from pyndn import Name
import re 
from datetime import datetime
import time

if len(sys.argv) < 2:
  print "usage: "+__file__+" [<log_file> | - ]"
  print "This script converts android timestamps to unix millisecond-precision timestamps"
  exit(1)

if __name__ == '__main__':
	logFile = sys.argv[1]
	lastBufferAppend = {}

	pattern = re.compile(".*(\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\.\d{3}).*")

	def processLine(p, line):
		m = pattern.match(line)
		if m:
			d=datetime.strptime(m.group(1), '%m-%d %H:%M:%S.%f')
			d=d.replace(year=datetime.now().year)
			ts = time.mktime(d.timetuple())+float(d.microsecond)/1e6
			line = line.replace(m.group(1), str(ts))
		sys.stdout.write(line)

	if logFile == '-':
		for line in sys.stdin:
			processLine(pattern, line)
	else:
		with open(logFile) as f:
			for line in f:
				processLine(pattern,line)  
