#!/usr/bin/env python

# slices consumer log into smaller files per runs

import linecache
import ndnlog
import sys
from ndnlog import NdnLogToken
from enum import Enum
from collections import OrderedDict
import re
import getopt

verbose = False
output = None

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
def setupRunFile(runNo):
  global output
  if output:
    output.close()
  output = open("run"+str(runNo)+"-log.stat", 'w')


def printKeywordDataBlock(kw):
  global output
  output.write(str(kw))

def onRebuffering(timestamp, match, userData):
  global output
  log("rebuffering "+match.group('rebuf_no')+" see "+output.name)
  runNo = userData['userData']['run']
  runNo += 1
  userData['userData']['run'] = runNo
  setupRunFile(runNo)
  return True

def onKeywordFound(timestamp, match, userData):
  global output, lineNo, logFile1
  #kwBlock = match.group('value')
  kwBlock = linecache.getline(logFile1, lineNo)
  printKeywordDataBlock(kwBlock)
  lineNo += 1
  return True

def run(logFile, keywords, sliceruns):
  global output, lineNo, logFile1

  keywordRegexString = "(?P<value>\S+)\n?"
  keywordParsingActions = {}
  keywordParsingActions['pattern'] = ndnlog.compileNdnLogPattern('.*', '.*', keywordRegexString)
  keywordParsingActions['tfunc'] = ndnlog.DefaultTimeFunc
  keywordParsingActions['func'] = onKeywordFound

  rebufferingRegexString = 'rebuffering #(?P<rebuf_no>[0-9]+) seed (?P<seed>[0-9]+) key (?P<key>[0-9]+) delta (?P<delta>[0-9]+) curent w (?P<cur_w>[0-9-]+) default w (?P<default_w>[0-9-]+)'
  rebufferingActions = {}
  rebufferingActions['pattern'] = ndnlog.compileNdnLogPattern(NdnLogToken.warning.__str__(), '.consumer-pipeliner', rebufferingRegexString)
  rebufferingActions['tfunc'] = ndnlog.DefaultTimeFunc
  rebufferingActions['func'] = onRebuffering
  rebufferingActions['userdata'] = {'run':0}

  lineNo = 1
  setupRunFile(0)
  logFile1 = logFile
  linecache.getline(logFile1, lineNo)

  ndnlog.parseLog(logFile, [rebufferingActions, keywordParsingActions])
  output.close()

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
    opts, args = getopt.getopt(sys.argv[1:], "vsf:", ["-v", "-slice", "log="])
  except getopt.GetoptError as err:
    print str(err)
    usage()
    sys.exit(2)
  for o, a in opts:
    if o in ("-f", "--log"):
      logFile = a
    elif o in ("-v"):
      verbose = True
    elif o in ("-s", "--slice"):
      sliceruns = True
    else:
      assert False, "unhandled option "+o
  if not logFile:
    usage();
  run(logFile, keywords, sliceruns)

if __name__ == '__main__':
  main()
