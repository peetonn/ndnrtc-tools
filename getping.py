#!/usr/bin/env python

# this script takes tests folder as an argument
# it assumes that each subfolder has hub name and contains
# log files from the test run
# hub subfolder should contain following files:
# - ndnping.log - output from ndnping tool
# - ping.log - output from ping tool
# - summary.txt - output from analyze.py script
# it will read these files and output 5-column table per hub 
# per each fetching phase of a consumer:
# 	rtc RTT est	NDN ping 	NDN ping var 	IP Ping 	IP Ping var

import sys
import getopt
import os
import glob
import re
import numpy

ndnping = "ndnping.log"
ping = "ping.log"
summary = "summary.txt"
verbose = False

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
def getPing(file):
	rtts = []
	regex = re.compile('time=(?P<rtt>[0-9.]+)')
	for line in open(file):
		m = regex.search(line)
		if m:
			rttValue = float(m.group('rtt'))
			rtts.append(rttValue)
	if len(rtts):
		return [numpy.mean(rtts), numpy.var(rtts)]
	return [0,0]


def getNdnPing(file):
	rtts = []
	regex = re.compile('Round Trip Time = (?P<rtt>[0-9.]+)')
	for line in open(file):
		m = regex.search(line)
		if m:
			rttValue = float(m.group('rtt'))
			rtts.append(rttValue)
	if len(rtts):
		return [numpy.mean(rtts), numpy.var(rtts)]
	return [0,0]

def getRttEst(file):
	rttEst = []
	regex = re.compile('rtt est\t(?P<rtt>[0-9.]+)')
	for line in open(file):
		m = regex.search(line)
		if m:
			rttEst.append(float(m.group('rtt')))
	return rttEst

def run(folder):
	global ping, ndnping, summary
	hubFolders = os.listdir(folder)
	for hubFolder in hubFolders:
		ndnpingFile = os.path.join(folder, hubFolder, ndnping)
		if not os.path.isfile(ndnpingFile):
			error("couldn't find file "+ndnpingFile)
			continue
		pingFile = os.path.join(folder, hubFolder, ping)
		if not os.path.isfile(pingFile):
			error("couldn't find file "+pingFile)
			continue
		summaryFile = os.path.join(folder, hubFolder, summary)
		if not os.path.isfile(summaryFile):
			error("couldn't find file "+summaryFile)
			continue
		log("extracting data for "+hubFolder)
		pingRtt, pingVar = getPing(pingFile)
		ndnRtt, ndnRttVar = getNdnPing(ndnpingFile)
		rttEst = getRttEst(summaryFile)
		print hubFolder
		for rttEstimation in rttEst:
			print "{0:.2f}\t{1:0.2f}\t{2:0.2f}\t{3:0.2f}\t{4:0.2f}".format(rttEstimation, ndnRtt, ndnRttVar, pingRtt, pingVar)

#******************************************************************************
def usage():
	print "usage: "+sys.argv[0]+" -f<tests_folder>"
	sys.exit(0)

def main():
	global verbose
	try:
		opts, args = getopt.getopt(sys.argv[1:], "vf:", ["-v", "test-folder="])
	except getopt.GetoptError as err:
		print str(err)
		usage()
		sys.exit(2)
	for o, a in opts:
		if o in ("-f", "--test-folder"):
			testFolder = a
		elif o in ("-v"):
			verbose = True
		else:
			assert False, "unhandled option "+o
	if not 'testFolder' in locals():
		usage();
	run(testFolder)

if __name__ == '__main__':
	main()
