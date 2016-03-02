# this script takes tests folder as an argument
# it assumes that each testrun subfolder contains
# log files from the test run in subfolders per consumer 
# consumer subfolder should contain following files:
# - ndnping.log - output from ndnping tool
# - ping.log - output from ping tool
# - summary.txt - output from analyze.py script
# it will read these files and output table per testrun 
# per each fetching phase of each consumer:
#	run time	rtt prime	rtt est	ndnping	ndnping var	ping	ping var	Dgen	Darr	lambda d	lambda	buf est	buf play	buf tar	prod rate
#
# testrun folders will be captioned on a separate line
# consumer folders will be captioned on a separate line

import sys
import getopt
import os
import glob
import re
import numpy
from analyze import StatKeyword

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

summaryRegex = re.compile('run\s(?P<run>[0-9]+)\sts\s(?P<timestamp>[0-9]+)\schase time\s(?P<chase_time>[0-9]+)\srun time\s(?P<run_time>[0-9]+)\sDgen\s(?P<Dgen>[0-9.]+)\sDarr\s(?P<Darr>[0-9.]+)\sbuf tar\s(?P<buf_tar>[0-9.]+)\sbuf est\s(?P<buf_est>[0-9.]+)\sbuf play\s(?P<buf_play>[0-9.]+)\srtt est\s(?P<rtt_est>[0-9.]+)\srtt prime\s(?P<rtt_prime>[0-9.]+)\slambda d\s(?P<lambda_d>[0-9.]+)\slambda\s(?P<lambda>[0-9.]+)')
def getSummary(file):
	summary = []
	for line in open(file):
		m = summaryRegex.search(line)
		if m:
			run = {}
			run['run_time'] = float(m.group('run_time'))
			run[StatKeyword.Dgen] = float(m.group('Dgen'))
			run[StatKeyword.Darr] = float(m.group('Darr'))
			run[StatKeyword.bufTarget] = float(m.group('buf_tar'))
			run[StatKeyword.bufEstimate] = float(m.group('buf_est'))
			run[StatKeyword.bufPlayable] = float(m.group('buf_play'))
			run[StatKeyword.rttEst] = float(m.group('rtt_est'))
			run[StatKeyword.rttPrime] = float(m.group('rtt_prime'))
			run[StatKeyword.lambdaD] = float(m.group('lambda_d'))
			run[StatKeyword.lambdaC] = float(m.group('lambda'))
			summary.append(run)
	return summary

def run(folder):
	global ping, ndnping, summary
	r = re.compile('consumer-(?P<consumer_name>.*)\.txt')
	testrunFolders = os.listdir(folder)
	for testrunFolder in testrunFolders:
		if not os.path.isdir(os.path.join(folder, testrunFolder)):
			continue
		consumerFolders = os.listdir(os.path.join(folder, testrunFolder))
		if len(consumerFolders):
			print testrunFolder
			for consumerFolder in consumerFolders:
				if not os.path.isdir(os.path.join(folder, testrunFolder, consumerFolder)):
					continue
				hubFolders = os.listdir(os.path.join(folder, testrunFolder, consumerFolder))
				if len(hubFolders) > 0:
					for hubFolder in hubFolders:
						ndnpingFile = os.path.join(folder, testrunFolder, consumerFolder, hubFolder, ndnping)
						if not os.path.isfile(ndnpingFile):
							error("couldn't find file "+ndnpingFile)
							continue
						pingFile = os.path.join(folder, testrunFolder, consumerFolder, hubFolder, ping)
						if not os.path.isfile(pingFile):
							error("couldn't find file "+pingFile)
							continue
						hubFolderPath = os.path.join(folder, testrunFolder, consumerFolder, hubFolder)
						pingRtt, pingVar = getPing(pingFile)
						ndnRtt, ndnRttVar = getNdnPing(ndnpingFile)
						summaryFiles = glob.glob(os.path.join(folder, testrunFolder, consumerFolder, hubFolder)+"/summary-*.txt")
						#print summaryFiles
						if len(summaryFiles) > 0:
							for summaryFile in summaryFiles:
								log("extracting data for "+summaryFile)								
								summ = getSummary(summaryFile)
								i = 0
								m = r.search(summaryFile)
								consumerName = m.group('consumer_name') if m else summaryFile
								print consumerName
								for run in summ:
									i += 1
									if run['run_time'] > 0:
										sys.stdout.write(consumerFolder + "\t"+str(len(summ))+"\n")

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
