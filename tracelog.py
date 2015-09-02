#!/usr/bin/env python

import ndnlog
import sys
from ndnlog import NdnLogToken
from enum import Enum
from collections import OrderedDict
import re
import readchar
import numpy

NextFrame='\x1b[B'
PrevFrame='\x1b[A'
SkipFrames='\x1b[C'
RevertFrames='\x1b[D'
TillRebuffering='r'
PrintBuffer='b'
Exit='\x03'

if len(sys.argv) < 2:
  print "usage: "+__file__+" <log_file>"
  print ""
  print "\t"+__file__+" may be used to interactively analyze consumer log files. It parses log file"
  print "\tand collects all available statistic information, as well as the state of the buffer."
  print "\tScript iteratively parses log file until it meets log entry about new incoming data."
  print "\tIt pauses there and prints out all main stat info it could gather by this moment."
  print "\tUser is then able to proceed or step backwards on 1- and 10-iterations granularity."
  print "\tIf log contains data about buffer state, it will be gathered and can be printed by pressing '"+PrintBuffer+"'"
  print "\tControls:"
  print "\t\tRight arrow - move to next iteration"
  print "\t\tLeft arrow - move to previous iteration"
  print "\t\tUp arrow - move +10 iterations forward"
  print "\t\tDown arrow - move -10 iterations backward"
  print "\t\t"+TillRebuffering+" - fastforward till rebuffering is encoutered"
  print "\t\t"+PrintBuffer+" - print current buffer state"
  print "\tLog file should contain statistics information (STAT level) and (optionally) buffer state "
  print "\tinformation (level TRACE)"
  print ""
  exit(1)

class StatKeyword(Enum):
  Dgen = 1
  Darr = 2
  bufTarget = 3
  bufEstimate = 4
  bufPlayable = 5
  rttEst = 6
  rttPrime = 7
  lambdaD = 8
  lambdaC = 9

  def __str__(self):
    return {StatKeyword.Dgen:'Dgen', StatKeyword.Darr:'Darr',\
    StatKeyword.bufTarget:'buf tar', StatKeyword.bufEstimate:'buf est', StatKeyword.bufPlayable:'buf play',\
    StatKeyword.rttEst:'rtt est', StatKeyword.rttPrime:'rtt prime',
    StatKeyword.lambdaD:'lambda d', StatKeyword.lambdaC:'lambda'}[self]

def statEntryRegex(statEntry):
  return str(statEntry)

statRegexString = '(?P<stat_entry>'+statEntryRegex(StatKeyword.Dgen)+'|'+statEntryRegex(StatKeyword.Darr)+'|'+\
  statEntryRegex(StatKeyword.bufTarget)+'|'+statEntryRegex(StatKeyword.bufEstimate)+'|'+statEntryRegex(StatKeyword.bufPlayable)+'|'+\
  statEntryRegex(StatKeyword.rttEst)+'|'+statEntryRegex(StatKeyword.rttPrime)+'|'+\
  statEntryRegex(StatKeyword.lambdaD)+'|'+statEntryRegex(StatKeyword.lambdaC)+')\\t(?P<value>[0-9.-]+)'
statRegex = re.compile(statRegexString)

def timeFunc(match):
  global runData
  ts = int(match.group('timestamp'))
  lastTs = runData['lastTimestamp']
  if lastTs != 0:
    runData['iterLen'] = ts-lastTs
  runData['lastTimestamp'] = ts
  return runData['lastTimestamp']

def printData(runData):
  global currentAppFrameIdx, appFrames
  if currentAppFrameIdx > 0:
    prevData = appFrames[currentAppFrameIdx-1]
    nData = runData['dataNo']-prevData['dataNo']
  else:
    nData = 1
  print ""
  print("[{0:5}]".format(currentAppFrameIdx)+" Line #"+str(runData['lineNo'])+" Run #"+str(runData['runNo'])+\
    " Timestamp "+str(runData['lastTimestamp'])+" Last iter length {0}ms ({1:.2f}sec)".format(runData['iterLen'], float(runData['iterLen'])/1000))
  print "\tINTERESTS SENT\tcurrent #"
  print "\t{0}\t\t{1}".format(runData['nInterests'], runData['interestNo'])
  print "\tDATA RECEIVED\tcurrent #"
  print "\t{0}\t\t{1}".format(nData, runData['dataNo'])
  print "\tRTT'\tRTT est\tDarr\tDgen\tl_D\tl\tBuf est\tplay\ttarget"
  print "\t{0:.2f}\t{1:.2f}\t{2:.2f}\t{3:.2f}\t{4:.2f}\t{5:.2f}\t{6:.2f}\t{7:.2f}\t{8:.2f}".format(runData[str(StatKeyword.rttPrime)],\
    runData[str(StatKeyword.rttEst)], runData[str(StatKeyword.Darr)], runData[str(StatKeyword.Dgen)], runData[str(StatKeyword.lambdaD)],\
    runData[str(StatKeyword.lambdaC)], runData[str(StatKeyword.bufEstimate)], runData[str(StatKeyword.bufPlayable)],\
    runData[str(StatKeyword.bufTarget)])
  print ""

def driveTrace():
  global nIterToSkip, currentAppFrameIdx, appFrames, skipTillRebuffering, rebufferingHit
  try:
    if nIterToSkip > 0:
      nIterToSkip -= 1
    elif skipTillRebuffering:
      if rebufferingHit:
        rebufferingHit = False
        skipTillRebuffering = False
    else:
      done = False
      while not done:
        sys.stdout.write("Up/Down - next/prev iter; Left/Right - next/prev 10 iter ")
        key = readchar.readkey()
        print ""
        if key == Exit:
          done = True
          exit(0)
        elif key == NextFrame:
          done = True
          if currentAppFrameIdx == len(appFrames)-1:
            pass
          else:
            currentAppFrameIdx += 1
            printData(appFrames[currentAppFrameIdx])
            driveTrace()
        elif key == PrevFrame:
          done = True
          if currentAppFrameIdx > 0: 
            currentAppFrameIdx -= 1
            printData(appFrames[currentAppFrameIdx])
            driveTrace()
          else: done = False
        elif key == SkipFrames: 
          done = True
          nIterToSkip += 10
        elif key == RevertFrames:
          done = True
          if currentAppFrameIdx >= 10:
            currentAppFrameIdx -= 10
            printData(appFrames[currentAppFrameIdx])
            driveTrace()
          else: done = False
        elif key == TillRebuffering:
          skipTillRebuffering = True
          rebufferingHit = False
          done = True
        elif key == PrintBuffer:
          print runData['bufferState']
  except SyntaxError:
    pass

def onRebuffering(timestamp, match, userData):
  global runData, rebufferingHit
  rebufferingHit = True
  return True

def onInterest(timestamp, match, userData):
  global runData
  runData['interestNo'] = int(match.group('frame_no'))
  runData['nInterests'] += 1
  return True

def onData(timestamp, match, userData):
  global runData, appFrames, currentAppFrameIdx, statBlock
  runData['iter'] += 1
  runData['lineNo'] = userData['lineNo']
  runData['dataNo'] = int(match.group('frame_no'))
  for statKey in runData['stats'].keys():
    runData[statKey] = numpy.mean(runData['stats'][statKey])
  appFrames.append(runData.copy())
  printData(runData)
  driveTrace()
  currentAppFrameIdx += 1
  runData['stats'] = statBlock.copy()
  runData['nInterests'] = 0
  return True

def onStatEntry(timestamp, match, userData):
  global runData
  for m in statRegex.finditer(match.group('message')):
    statEntry = m.group('stat_entry')
    value = float(m.group('value'))
    if not statEntry in statBlock.keys():
      print str(statEntry) + ' is not in stat block: '+str(statBlock)
    else:
      runData['stats'][statEntry].append(value)
  return True

def onBufferDumplineDetected(timestamp, match, userData):
  global framePopped, runData

  if framePopped:
    frame = ndnlog.Frame(match)
    runData['bufferState'].addFrame(timestamp, frame)
  return True

def onFrameMoved(timestamp, match, userData):
  global framePopped, currentBufferState, runData
  frame = ndnlog.Frame(match)
  if match.group('move') == 'pop':
    poppedFrame = ndnlog.Frame(match)
    runData['bufferState'] = ndnlog.BufferState()
    runData['bufferState'].addFrame(timestamp, poppedFrame)
    framePopped = True
  else:
    framePopped = False
  return True

if __name__ == '__main__':
  logFile = sys.argv[1]

  currentBufferState = None
  framePopped = False
  poppedFrame = None  
  nIterToSkip = 0
  currentAppFrameIdx = 0
  skipTillRebuffering = False
  appFrames = []
  statBlock = OrderedDict([(str(StatKeyword.Dgen),[]), (str(StatKeyword.Darr),[]), (str(StatKeyword.bufTarget),[]), (str(StatKeyword.bufEstimate),[]),\
  (str(StatKeyword.bufPlayable),[]), (str(StatKeyword.rttEst),[]), (str(StatKeyword.rttPrime),[]), (str(StatKeyword.lambdaD),[]), (str(StatKeyword.lambdaC),[])])
  runData = {'lineNo':0, 'iter':0, 'runNo':0, 'lastTimestamp':0, 'iterLen':0, 'interestNo':0, 'nInterests':0,\
  'dataNo':0, 'chaseTime':0, 'runStartTime':0, 'stats':statBlock.copy(), 'bufferState':None}

  rebufferingRegexString = 'rebuffering #(?P<rebuf_no>[0-9]+) seed (?P<seed>[0-9]+) key (?P<key>[0-9]+) delta (?P<delta>[0-9]+) curent w (?P<cur_w>[0-9]+) default w (?P<default_w>[0-9]+)'
  rebufferingActions = {}
  rebufferingActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.warning.__str__(), '.consumer-pipeliner', rebufferingRegexString)
  rebufferingActions['tfunc'] = ndnlog.DefaultTimeFunc
  rebufferingActions['func'] = onRebuffering

  interestExpressRegex  = 'express\t'+ndnlog.NdnRtcNameRegexString
  interestExpressActions = {}
  interestExpressActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.stat.__str__(), '.iqueue', interestExpressRegex)
  interestExpressActions['tfunc'] = ndnlog.DefaultTimeFunc
  interestExpressActions['func'] = onInterest

  dataReceivedRegex  = 'data '+ndnlog.NdnRtcNameRegexString
  dataReceivedActions = {}
  dataReceivedActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.stat.__str__(), '.consumer-pipeliner', dataReceivedRegex)
  dataReceivedActions['tfunc'] = timeFunc
  dataReceivedActions['func'] = onData

  statEntryActions = {}
  statEntryActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.stat.__str__(), '.*', statRegexString)
  statEntryActions['tfunc'] = ndnlog.DefaultTimeFunc
  statEntryActions['func'] = onStatEntry

  parseBuffer = {}
  parseBuffer['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', ndnlog.Frame.BufferFrameStringPattern)
  parseBuffer['tfunc'] = ndnlog.DefaultTimeFunc
  parseBuffer['func'] = onBufferDumplineDetected

  moveFrame = {}
  moveFrame['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.trace.__str__(), '.*', '(?P<move>(pop|push)).*'+ndnlog.Frame.FrameStringPattern)
  moveFrame['tfunc'] = ndnlog.DefaultTimeFunc
  moveFrame['func'] = onFrameMoved

  ndnlog.parseLog(logFile, [parseBuffer, moveFrame, rebufferingActions, interestExpressActions, statEntryActions, dataReceivedActions])


