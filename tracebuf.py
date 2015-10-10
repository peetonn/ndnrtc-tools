#!/usr/bin/env python

import ndnlog
import sys
import re
from ndnlog import NdnLogToken
import getopt

bufferStates = []
currentBufferState = None
framePopped = False
printAll = False
waitForUserInput = True
poppedFrame = None
logFile = None
lastLambda = 0

def onLambdaDetected(timestamp, match, userData):
	global lastLambda
	lastLambda = match.group('lambda_d')
	return True

def onBufferDumplineDetected(timestamp, match, userData):
	global framePopped
	global currentBufferState
	global bufferStates
	global printAll

	if framePopped:
		frame = ndnlog.Frame(match)
		currentBufferState.addFrame(timestamp, frame)
	return True

def printCurrentBufferState():
	global waitForUserInput, lastLambda
	if printAll:
		print "lambda_d "+str(lastLambda)
		print currentBufferState
	else:
		if len(currentBufferState.frames):
			if currentBufferState.frames[0].assembledLevel < 100:
				print "lambda_d "+lastLambda
				print currentBufferState
			else:
				return
		else:
			print "lambda_d "+lastLambda
			print currentBufferState
	if waitForUserInput:
		try:
			input("Press enter to continue")
		except SyntaxError:
			pass

def onFrameMoved(timestamp, match, userData):
	global framePopped
	global currentBufferState
	global printAll
	frame = ndnlog.Frame(match)
	# if match.group('move') == 'pop':
	if currentBufferState:
		bufferStates.append(currentBufferState)
		printCurrentBufferState()
	poppedFrame = ndnlog.Frame(match)
	currentBufferState = ndnlog.BufferState()
	currentBufferState.addFrame(timestamp, poppedFrame)
	# if match.group('move') == 'pop':
		# framePopped = True
	# else:
	framePopped = True
	# else:
	# 	framePopped = False
	return True

def usage():
	print 'usage: '+sys.argv[0] + ' -f <log_file> [-a] [-n]'
	print '\t -a: print all buffer states (in normal mode only states with incomplete 1st frame are printed)'
	print '\t -n: do not stop for user input'
	print ""
	print "\tThis script is useful to interactively iterate through the buffer states or to locate 'bad' buffer states - "
	print "\tones, where first frame (the frame that should be taken out by playout mechanism) is incomplete. Log file should"
	print "\tcontain buffer state information (TRACE level)"

if __name__ == '__main__':
	try:
		opts, args = getopt.getopt(sys.argv[1:], "f:an", ["-file", "-all", "-nostop"])
	except getopt.GetoptError as err:
		print str(err)
		usage()
		sys.exit(2)
	for o, a in opts:
		if o in ("-f", "--file"):
			logFile = a
		elif o in ("-a", "--all"):
			printAll = True
		elif o in ("-n", "--nostop"):
			waitForUserInput = False
		else:
			assert False, "unhandled option "+o
	if not logFile:
		usage()
		exit(1)

	trackLambda = {}
	trackLambda['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.stat.__str__(), '.*', "lambda d\s(?P<lambda_d>[0-9.-]+)")
	trackLambda['tfunc'] = ndnlog.DefaultTimeFunc
	trackLambda['func'] = onLambdaDetected

	parseBuffer = {}
	parseBuffer['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', ndnlog.Frame.BufferFrameStringPattern)
	parseBuffer['tfunc'] = ndnlog.DefaultTimeFunc
	parseBuffer['func'] = onBufferDumplineDetected

	moveFrame = {}
	moveFrame['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', '(?P<move>(pop|push)).*'+ndnlog.Frame.FrameStringPattern)
	moveFrame['tfunc'] = ndnlog.DefaultTimeFunc
	moveFrame['func'] = onFrameMoved

	ndnlog.parseLog(logFile, [moveFrame, trackLambda, parseBuffer])
