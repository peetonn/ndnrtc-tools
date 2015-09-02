#!/usr/bin/env python

# this script takes tests folder as an argument
# it assumes that each subfolder has hub name and contains
# log files from the test run
# hub subfolder should contain following files:
# - summary.txt - output from analyze.py script
# it will read these files and output table per hub 
# per each fetching phase:
# 	RTTprime	RTTest	Dgen	Darr	LambdaD	Lambda	BufEst	BufPlay	BufTar
#

import sys
import getopt
import os
import glob
import re
import numpy

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
def getStats(file, statKeys):
	allStats = []
	for line in open(file):
		stats = {}
		for statKey in statKeys:
			regex = re.compile(str(statKey)+'\t(?P<val>[0-9.-]+)')
			m = regex.search(line)
			if m:
				stats[statKey] = float(m.group('val'))
		if len(stats):
			allStats.append(stats)
	return allStats

def run(folder):
	global ping, ndnping, summary
	hubFolders = os.listdir(folder)
	headers = ["run time", "rtt prime", "rtt est", "Dgen", "Darr", "lambda d", "lambda", "buf est", "buf play", "buf tar"]
	for hdr in headers:
		sys.stdout.write("%s\t"%hdr)
	sys.stdout.write("\n")
	for hubFolder in hubFolders:
		summaryFile = os.path.join(folder, hubFolder, summary)
		if not os.path.isfile(summaryFile):
			error("couldn't find file "+summaryFile)
			continue
		log("extracting data for "+hubFolder)
		allStats = getStats(summaryFile, headers)
		# print str(allStats)
		print hubFolder
		for stats in allStats:
			for statKey in headers:
				sys.stdout.write("%.2f\t"%stats[statKey])
			if len(stats): sys.stdout.write("\n")

#******************************************************************************
def usage():
	print "usage: "+sys.argv[0]+" --f<tests_folder>"
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
