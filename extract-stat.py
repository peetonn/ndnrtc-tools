#!/usr/bin/env python

# extracts statistics from consumer log
# example use: extract-stat.py -f consumer-test2-camera.log -k "new state,buf est,buf tar,buf play,rtt est,D arr,lambda d" -v
# will output tab-delimited columns timestamp, run #, new state, buf est, buf tar, buf play, rtt est, D arr, lambda d
# where timestamp and run # - millisecond timestamp and run (continuous playback before rebuffering) number respectively

import ndnlog
import sys
from ndnlog import NdnLogToken
from enum import Enum
from collections import OrderedDict
import re
import getopt

verbose = False
output = sys.stdout
runLog = None
runNo = 0

def log(msg):
  global verbose
  if verbose:
    sys.stderr.write(msg+"\n")

def error(msg):
  global verbose
  if verbose:
    sys.stderr.write("error: "+msg+"\n")

def fatal(msg):
  global verbose
  if verbose:
    sys.stderr.write(msg+"\n")
  exit(1)

#******************************************************************************
# def setupRunFile(runNo):
#   global output, runLog
#   if output:
#     output.close()
#   if runLog:
#     runLog.close()
#   output = open("run"+str(runNo)+".stat", 'w')
#   runLog = open("run"+str(runNo)+".log", 'w')

def printKeywordHeader(kw):
  global output
  output.write('ts\trun#\t')
  for key in kw.keys():
    output.write(str(key)+'\t')
  output.write('\n')

def printKeywordDataBlock(timestamp, userData):
  global output, runNo
  kw = userData['kw']
  output.write(str(timestamp)+'\t'+str(runNo)+'\t')
  for key in kw.keys():
    output.write(str(kw[key]))
    if kw.keys().index(key) != len(kw)-1:
      output.write('\t')
  output.write('\n')

def onRebuffering(timestamp, match, userData):
  global output, runNo
  log("rebuffering "+match.group('rebuf_no')+" see "+output.name)
  kw = userData['userData']['kw']
  runNo += 1
  return True

def onKeywordFound(timestamp, match, userData):
  kwBlock = userData['userData']
  kwBlock[match.group('keyword')] = match.group('value')
  printKeywordDataBlock(timestamp, kwBlock)
  return True

def onKeywordEntry(timestamp, match, userData):
  global statBlock, lastTimestamp
  for m in statRegex.finditer(match.group('message')):
    statEntry = m.group('stat_entry')
    value = float(m.group('value'))
    if not statEntry in statBlock.keys():
      print str(statEntry) + ' is not in stat block: '+str(statBlock)
    else:
      statBlock[statEntry].append(value)
  return True

def run(logFile, keywords, sliceruns):
  global output
  keywordNames = ""
  keywordDataBlock = OrderedDict()
  for keyword in keywords:
    keywordDataBlock[keyword] = ""
    if keywords.index(keyword) != len(keywords)-1:
      keywordNames += keyword.rstrip()+"|"
    else:
      keywordNames += keyword.rstrip()
  
  keywordRegexString = "(?P<keyword>"+keywordNames+")\s(?P<value>\S+)\s?"
  keywordParsingActions = {}
  keywordParsingActions['pattern'] = ndnlog.compileNdnLogPattern('.*', '.*', keywordRegexString)
  keywordParsingActions['tfunc'] = ndnlog.DefaultTimeFunc
  keywordParsingActions['func'] = onKeywordFound
  keywordParsingActions['userdata'] = {'run':0, 'kw':keywordDataBlock}

  rebufferingRegexString = 'rebuffering #(?P<rebuf_no>[0-9]+) seed (?P<seed>[0-9]+) key (?P<key>[0-9]+) delta (?P<delta>[0-9]+) curent w (?P<cur_w>[0-9-]+) default w (?P<default_w>[0-9-]+)'
  rebufferingActions = {}
  rebufferingActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.warning.__str__(), '.consumer-pipeliner', rebufferingRegexString)
  rebufferingActions['tfunc'] = ndnlog.DefaultTimeFunc
  rebufferingActions['func'] = onRebuffering
  rebufferingActions['userdata'] = {'run':0, 'kw':keywordDataBlock}

  # setupRunFile(0)

  printKeywordHeader(keywordDataBlock)
  ndnlog.parseLog(logFile, [rebufferingActions, keywordParsingActions])
  # output.close()

#******************************************************************************
def usage():
  print "usage: "+sys.argv[0]+" -f<consumer_log> -k<keywords>"
  sys.exit(0)

def main():
  global verbose
  keywords = None
  logFile = None
  sliceruns = False
  try:
    opts, args = getopt.getopt(sys.argv[1:], "vsk:f:", ["-v", "-slice","keywords=", "log="])
  except getopt.GetoptError as err:
    print str(err)
    usage()
    sys.exit(2)
  for o, a in opts:
    if o in ("-f", "--log"):
      logFile = a
    elif o in ("-v"):
      verbose = True
    elif o in ("-k", "--keywords"):
      keywords = a.split(',')
    elif o in ("-s", "--slice"):
      sliceruns = True
    else:
      assert False, "unhandled option "+o
  if not logFile or not keywords or len(keywords) == 0:
    usage();
  run(logFile, keywords, sliceruns)

if __name__ == '__main__':
  main()
