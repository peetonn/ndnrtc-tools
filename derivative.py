#!/usr/bin/env python

import sys
from pyndn import Name
import getopt
from scipy.interpolate import interp1d

if len(sys.argv) < 2:
  print "usage: "+__file__+" [<csv_file> | - ] [-d <delimiter>] [-c <column>] [-i <interval>] [-m <multiply>]"
  print ""
  print "Calculates derivative of a selected column in a CSV file. If no column is specified, "
  print "calculates derivative on all columns. Optionally, may specify an arithmetic multiplier"
  print "which will be applied to the column value before calculating derivative (for example,"
  print "this is useful for converting bytes to bits before calculating bitrate)."
  print "May optionally specify an interval, default is 1 second."
  print "Assumes that first column is a timestamp in milliseconds."
  print ""
  exit(1)

if __name__ == '__main__':
	try:
		opts, args = getopt.getopt(sys.argv[1:], "d:c:i:m:", [])
	except getopt.GetoptError as err:
		print str(err)
		sys.exit(2)

	delimiter = "\t"
	interval = 1
	selectedColumn = None
	multiply = 1 # for bytes -> bits conversion, set to 8
	for o, a in opts:
		if o in ("-d"):
			delimiter = a
		elif o in ("-c"):
			selectedColumn = a
		elif o in ("-i"):
			interval = float(a)
		elif o in ("-m"):
			multiply = float(a)
		else:
			assert False, "unhandled option "+o
	logFile = args[0]
	columns = None
	header = None
	window = None
	def getTuple(comps, columns, headers):
		t = {}
		for idx in columns:
			t[headers[idx]] = float(comps[idx])
		return t

	def processLine(line):
		global header, columns, window
		comps = line.strip().split(delimiter)
		try:
			if header == None: # intialize, assuming first line is a header
				header = comps
				if selectedColumn == None:
					columns = list(xrange(len(comps)))
				else:
					print header
					columns = [0, header.index(selectedColumn)]
				sys.stdout.write(line)
			else:
				t = getTuple(comps, columns, header) # {'timestamp':, 'bytesRcvd':}
				for k in t.keys():
					if not window or not k in window:
						if not window: window = {}
						window[k] = []
					if k == 'timestamp':
						window[k].append(t[k]) 
					else:
						window[k].append(t[k]*multiply) 
				# check whether it's time to calculate
				x1 = t['timestamp']/1000. # timestamps are in ms
				x0 = window['timestamp'][0]/1000.
				if x1-x0 > interval:
					xD = x0 + interval
					for k in t.keys():
						if k != 'timestamp':
							f = interp1d(window['timestamp'], window[k])
							y0 = window[k][0]
							yD = f(xD*1000)
							dY = (yD-y0)/(xD-x0)
							comps[header.index(k)] = str(dY)
							window[k] = [yD, t[k]]
					window['timestamp'] = [xD*1000, x1*1000]
					for c in comps:
						sys.stdout.write(c)
						if comps.index(c) != len(comps)-1:
							sys.stdout.write(delimiter)
					sys.stdout.write("\n")
		except Exception as err:
			print "Caught error on line '" + line + "': " + str(err)

	if logFile == '-':
		for line in sys.stdin:
			processLine(line)
	else:
		with open(logFile) as f:
			for line in f:
				processLine(line)  
