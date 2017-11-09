#!/usr/bin/env python

import requests
import sys
import re
import time
import getopt
import json
import os
import subprocess
import time
import errno
import stat
import json
import datetime
import threading
import thread
import signal
import operator

# input regex (?P<timestamp>\d+\.\d+)\s+.+onIncomingInterest\sface=\d+\sinterest=/icear/user/peter/ndnrtc/%FD%02/video/back_camera/vp9/d/(?P<input>\d+)/.*
# output regex (?P<timestamp>\d+\.\d+)\s+.+onOutgoingInterest\sface=\d+\sinterest=/icear/user/peter/ndnrtc/%FD%02/video/back_camera/vp9/d/(?P<output>\d+)/.*

firstLine = True
separator = '\t'
timestampGroupKwd = 'timestamp'
inputGroupKwd = 'input'
outputGroupKwd = 'output'
ordering = 'toi'
orderingIndexes = []
previousRecord = None
jsonFormatting = False
jsonPiggyback = None

def sortOutput():
	global ordering, orderingIndexes
	output = { 't' : ordering.find('t'), 'i': ordering.find('i'), 'o': ordering.find('o') }
	sortedOutput = sorted(output.items(), key=operator.itemgetter(1))
	for (k,v) in sortedOutput:
		orderingIndexes.append(k)

def printRecord(dataDict):
	global firstLine, jsonFormatting
	# if firstLine:
	# 	firstLine = False
	# 	i = 0
	# 	for k in orderingIndexes:
	# 		s = {'t' : 'ts', 'o': 'out', 'i': 'in'}[k]
	# 		i += 1
	# 		sys.stdout.write(s)
	# 		if i < len(orderingIndexes):
	# 			sys.stdout.write(separator)
	# 		else:
	# 			sys.stdout.write('\n')
	if jsonFormatting:
		if jsonPiggyback:
			dataDict.update(jsonPiggyback)
		sys.stdout.write(json.dumps(dataDict)+'\n')
	else:
		i = 0
		for k in orderingIndexes:
			i += 1
			if dataDict[k]:
				sys.stdout.write(dataDict[k])
			if i < len(orderingIndexes):
					sys.stdout.write(separator)
			else:
				sys.stdout.write('\n')

def isFullRecord(record):
	return record['t'] and record['i'] and record['o']

def printData(dataDict):
	global separator, orderingIndexes, previousRecord

	if isFullRecord(dataDict):
		if previousRecord:
			printRecord(previousRecord)
			previousRecord = None
		printRecord(dataDict)
	else: # check if can collapse
		if previousRecord:
			if previousRecord['t'] == dataDict['t']:
				# check if numbers are present in both recrods - then do not collapse
				if previousRecord['i'] and dataDict['i'] or previousRecord['o'] and dataDict['o']:
					printRecord(previousRecord)
					previousRecord = dataDict
				else: # some numbers are missing and safe to collapse
					previousRecord['i'] = dataDict['i'] if not previousRecord['i'] else previousRecord['i']
					previousRecord['o'] = dataDict['o'] if not previousRecord['o'] else previousRecord['o']
					printRecord(previousRecord)
					previousRecord = None
					# we do not save current record (dataDict), because its' data has been copied 
					# to the previousRecord and was printed out
			else: # print previous store this
				printRecord(previousRecord)
				previousRecord = dataDict
		else:
			previousRecord = dataDict

def processLine(line, inputRegex, outputRegex):
	global timestampGroupKwd, inputGroupKwd, outputGroupKwd
	mIn = inputRegex.match(line)
	mOut = outputRegex.match(line)
	timestamp = None
	inputVal = None
	outputVal = None
	if mIn:
		timestamp = mIn.group(timestampGroupKwd)
		inputVal = mIn.group(inputGroupKwd)
	if mOut:
		timestamp = mOut.group(timestampGroupKwd)
		outputVal = mOut.group(outputGroupKwd)
	if timestamp:
		printData({'t': timestamp, 'o':inputVal, 'i':outputVal})

def finalize():
	global previousRecord
	if previousRecord:
		printRecord(previousRecord)
		previousRecord = None

#******************************************************************************
def usage():
	print ""
	print "Usage: "+sys.argv[0]+" --input=<input-regex> --output=<output-regex> [--tail, --order=<column-ordering>, --json --json-piggyback=<key=value[,key=value]>] [<log_file> | -]"
	print ""
	print "\tThis script takes log file or stdinput (pass '-' for that) and parses it with"
	print "\tsupplied regular expressions."
	print "\tIf regex matches, it extracts groups '"+timestampGroupKwd+"' and '"+inputGroupKwd+"' (or '"+outputGroupKwd+"') and prints them in"
	print "\tcorresponding columns. The output is always a three-column: "+timestampGroupKwd+", "+outputGroupKwd+", "+inputGroupKwd+"."
	print "\tDefault ordering is timestamp-output-input, but it can be altered by passing "
	print "\t--order argument. For example, for timestamp-input-output ordering, pass '--order=tio'."
	print "\tSuch columns output is useful for printing scatter plots. If 'tail' argument is passed,"
	print "\tscript will block and monitor for new data in the file, otherwise - it parses file "
	print "\tfrom the beginning. Regular expressions MUST have groups '"+timestampGroupKwd+"', '"+inputGroupKwd+"'"
	print "\t(for input regex) and '"+outputGroupKwd+"' (for output regex)."
	print ""

def badStart(msg):
	print msg
	usage()
	exit(2)

def main():
	global ordering, jsonFormatting, jsonPiggyback
	try:
		opts, args = getopt.getopt(sys.argv[1:], "", ["input=", "output=", "tail", "order=", "json", "json-piggyback="])
	except getopt.GetoptError as err:
		print str(err)
		usage()
		exit(2)

	inputRegex = None
	outputRegex = None
	isTailing = False
	logFile = None

	if len(args) > 1:
		badStart("too many arguments supplied: "+str(args))
	elif len(args) == 1:
		logFile = args[0]

	for o,a in opts:
		if o in ("--input"):
			inputRegex = re.compile(a)
		elif o in ("--output"):
			outputRegex = re.compile(a)
		elif o in ("--tail"):
			isTailing = True
		elif o in ("--order"):
			if len(a) > 3: badStart("bad ordering provided")
			if 't' in a and 'i' in a and 'o' in a:
				ordering = a
			else:
				badStart("bad ordering provided")
		elif o in ("--json"):
			jsonFormatting = True
		elif o in ("--json-piggyback"):
			for pair in a.split(','):
				kv = pair.split('=')
				if len(kv) == 2:
					if not jsonPiggyback:
						jsonPiggyback = {}
					jsonPiggyback[kv[0]] = kv[1]
		else:
			assert False, "unhandled option "+o

	if not logFile:
		badStart("no filename supplied")
	if not inputRegex:
		badStart("no input regex supplied")
	if not outputRegex:
		badStart("no output regex supplied")

	sortOutput()
	if logFile == '-':
		for line in sys.stdin:
			processLine(line, inputRegex, outputRegex)
	elif not isTailing:
		with open(logFile) as f:
			for line in f:
				processLine(line, inputRegex, outputRegex)
	else: # watch file
		pass
	finalize()

if __name__ == '__main__':
	main()