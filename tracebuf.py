#!/usr/bin/env python

import ndnlog
import sys
import re
from ndnlog import NdnLogToken

bufferStates = []
currentBufferState = None
framePopped = False
printAll = False
poppedFrame = None

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
	if printAll:
		print currentBufferState
	else:
		if len(currentBufferState.frames):
			if currentBufferState.frames[0].assembledLevel < 100:
				print currentBufferState
			else:
				return
		else:
			print currentBufferState
	try:
		input("Press enter to continue")
	except SyntaxError:
		pass

def onFrameMoved(timestamp, match, userData):
	global framePopped
	global currentBufferState
	global printAll
	frame = ndnlog.Frame(match)
	if match.group('move') == 'pop':
		if currentBufferState:
				bufferStates.append(currentBufferState)
				printCurrentBufferState()
		poppedFrame = ndnlog.Frame(match)
		currentBufferState = ndnlog.BufferState()
		currentBufferState.addFrame(timestamp, poppedFrame)
		framePopped = True
	else:
		framePopped = False
	return True

if __name__ == '__main__':
	if len(sys.argv) < 2:
		print 'usage: '+sys.argv[0] + ' <log_file> [-a]'
		print '\t -a: print all buffer states (in normal mode only states with incomplete 1st frame are printed)'
		exit(1)

	logFile = sys.argv[1]
	if len(sys.argv) == 3 and sys.argv[2] == '-a':
		printAll = True

	parseBuffer = {}
	parseBuffer['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', ndnlog.Frame.BufferFrameStringPattern)
	parseBuffer['tfunc'] = ndnlog.DefaultTimeFunc
	parseBuffer['func'] = onBufferDumplineDetected

	moveFrame = {}
	moveFrame['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', '(?P<move>(pop|push)).*'+ndnlog.Frame.FrameStringPattern)
	moveFrame['tfunc'] = ndnlog.DefaultTimeFunc
	moveFrame['func'] = onFrameMoved

	ndnlog.parseLog(logFile, [moveFrame, parseBuffer])
