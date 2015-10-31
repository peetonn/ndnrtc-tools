#!/usr/bin/env python

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
from analyze_morestat import StatKeyword

ndnping = "ndnping.log"
ping = "ping.log"
summary = "summary.txt"
verbose = False
printRebufferingsOnly = False

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

#summaryRegex = re.compile('run\s(?P<run>[0-9-]+)\sts\s(?P<timestamp>[0-9]+)\schase time\s(?P<chase_time>[0-9]+)\srun time\s(?P<run_time>[0-9.-]+)\sDgen\s(?P<Dgen>[0-9.-]+)\sDarr\s(?P<Darr>[0-9.-]+)\sbuf tar\s(?P<buf_tar>[0-9.-]+)\sbuf est\s(?P<buf_est>[0-9.-]+)\sbuf play\s(?P<buf_play>[0-9.-]+)\srtt est\s(?P<rtt_est>[0-9.-]+)\srtt prime\s(?P<rtt_prime>[0-9.-]+)\slambda d\s(?P<lambda_d>[0-9.-]+)\slambda\s(?P<lambda>[0-9.-]+)')
summaryRegex = re.compile('run\s(?P<run>[0-9-]+)\sts\s(?P<timestamp>[0-9]+)\schase time\s(?P<chase_time>[0-9]+)\srun time\s(?P<run_time>[0-9.-]+)\sDgen\s(?P<Dgen>[0-9.-]+)\sDarr\s(?P<Darr>[0-9.-]+)\sbuf tar\s(?P<buf_tar>[0-9.-]+)\sbuf est\s(?P<buf_est>[0-9.-]+)\sbuf play\s(?P<buf_play>[0-9.-]+)\srtt est\s(?P<rtt_est>[0-9.-]+)\srtt prime\s(?P<rtt_prime>[0-9.-]+)\slambda d\s(?P<lambda_d>[0-9.-]+)\slambda\s(?P<lambda>[0-9.-]+)\srecover\s(?P<recover>[0-9.-]+)\sresc\s(?P<resc>[0-9.-]+)\srtx\s(?P<rtx>[0-9.-]+)\sdelta gop mismatch\s(?P<skipNoKey>[0-9.-]+)\sdelta incomplete\s(?P<skippedIncompleteDel>[0-9.-]+)\skey incomplete\s(?P<skippedIncompleteKey>[0-9.-]+)\sinvalid gop\s(?P<skippedBadGop>[0-9.-]+)\sunlock\s(?P<totalAcquiredFrames>[0-9.-]+)')
def getSummary(file):
	summary = []
	for line in open(file):
		m = summaryRegex.search(line)
		if m:
			run = {}
			run['run_time'] = float(m.group('run_time'))
			run['chase_time'] = float(m.group('chase_time'))
			run[StatKeyword.Dgen] = float(m.group('Dgen'))
			run[StatKeyword.Darr] = float(m.group('Darr'))
			run[StatKeyword.bufTarget] = float(m.group('buf_tar'))
			run[StatKeyword.bufEstimate] = float(m.group('buf_est'))
			run[StatKeyword.bufPlayable] = float(m.group('buf_play'))
			run[StatKeyword.rttEst] = float(m.group('rtt_est'))
			run[StatKeyword.rttPrime] = float(m.group('rtt_prime'))
			run[StatKeyword.lambdaD] = float(m.group('lambda_d'))
			run[StatKeyword.lambdaC] = float(m.group('lambda'))
			run[StatKeyword.rtx] = float(m.group('rtx'))
			run[StatKeyword.recovered] = float(m.group('recover'))
			run[StatKeyword.rescued] = float(m.group('resc'))
			run[StatKeyword.skipNoKey] = float(m.group('skipNoKey'))
			run[StatKeyword.skippedIncompleteDel] = float(m.group('skippedIncompleteDel'))
			run[StatKeyword.skippedIncompleteKey] = float(m.group('skippedIncompleteKey'))
			run[StatKeyword.skippedBadGop] = float(m.group('skippedBadGop'))
			run[StatKeyword.acquiredNum] = float(m.group('totalAcquiredFrames'))
			summary.append(run)
			# print "run['run_time']: "+str(run['run_time'] ) 
	return summary

def run(folder):
	global ping, ndnping, summary, printRebufferingsOnly
	r = re.compile('consumer-(?P<consumer_name>.*)\.txt')
	testrunFolders = sorted(os.listdir(folder))
	for testrunFolder in testrunFolders:
		if not os.path.isdir(os.path.join(folder, testrunFolder)):
			continue
		consumerFolders = sorted(os.listdir(os.path.join(folder, testrunFolder)))
		if len(consumerFolders):
			print testrunFolder
			for consumerFolder in consumerFolders:
				if not os.path.isdir(os.path.join(folder, testrunFolder, consumerFolder)):
					continue
				hubFolders = sorted(os.listdir(os.path.join(folder, testrunFolder, consumerFolder)))
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
								if printRebufferingsOnly == True:
									wrongRuns = 0
									avgChaseTime = 0
									avgrttEstTime = 0
									recoverSum = 0
									rescSum = 0
									skipNoKeySum = 0
									skippedIncompleteDelSum = 0
									skippedIncompleteKeySum = 0
									skippedBadGopSum = 0
									totalAcquiredFramesSum = 0 
									for run in summ:
										if run['run_time'] <= 0: 
											wrongRuns += 1
										else:
											avgChaseTime += run['chase_time']
											avgrttEstTime += run[StatKeyword.rttEst]
											recoverSum += run[StatKeyword.recovered]
											rescSum += run[StatKeyword.rescued]
											skipNoKeySum += run[StatKeyword.skipNoKey]
											skippedIncompleteDelSum += run[StatKeyword.skippedIncompleteDel]
											skippedIncompleteKeySum += run[StatKeyword.skippedIncompleteKey]
											skippedBadGopSum += run[StatKeyword.skippedBadGop]
											totalAcquiredFramesSum += run[StatKeyword.acquiredNum]

									if (len(summ)-wrongRuns)!=0:
										avgChaseTime = avgChaseTime/(len(summ)-wrongRuns)
										avgrttEstTime = avgrttEstTime/(len(summ)-wrongRuns)
									else:
										avgChaseTime = -1
										avgrttEstTime = -1
									if totalAcquiredFramesSum==0:
										totalAcquiredFramesSum=-1
									sys.stdout.write(consumerName + "\t"+str(len(summ)-wrongRuns)+"\t"+str(avgChaseTime)+"\t"+str(avgrttEstTime)+"\t"+str(recoverSum)+"\t"+str(rescSum)+"\t"+str(skipNoKeySum)+"\t"+str(skippedIncompleteDelSum)+"\t"+str(skippedIncompleteKeySum)+"\t"+str(skippedBadGopSum)+"\t"+str(totalAcquiredFramesSum)+"\n")
									#sys.stdout.write(consumerName + "\t"+str(len(summ)-wrongRuns)+"\t"+str(avgChaseTime)+"\t"+str(avgrttEstTime)+"\t"+str(recoverSum/totalAcquiredFramesSum*100)+"\t"+str(rescSum/totalAcquiredFramesSum*100)+"\t"+str(skipNoKeySum)+"\t"+str(skippedIncompleteDelSum)+"\t"+str(skippedIncompleteKeySum)+"\t"+str(skippedBadGopSum)+"\n")
								else:
									print consumerName
									for run in summ:
										i += 1								
										if run['run_time'] > 0:
											print "{0:.2f}\t{1:0.2f}\t{2:0.2f}\t{3:0.2f}\t{4:0.2f}\t{5:0.2f}\t{6:0.2f}\t{7:0.2f}\t{8:0.2f}\t{9:0.2f}\t{10:0.2f}\t{11:0.2f}\t{12:0.2f}\t{13:0.2f}\t{14:0.2f}\t{15:0.2f}\t{16:0.2f}\t{17:0.2f}\t{18:0.2f}\t{19:0.2f}\t{20:0.2f}\t{21:0.2f}".format(run['run_time'], run[StatKeyword.rttPrime], \
												run[StatKeyword.rttEst], ndnRtt, ndnRttVar, pingRtt, pingVar,\
												run[StatKeyword.Dgen], run[StatKeyword.Darr], run[StatKeyword.lambdaD], run[StatKeyword.lambdaC], \
												run[StatKeyword.bufEstimate], run[StatKeyword.bufPlayable], run[StatKeyword.bufTarget], \
												run[StatKeyword.rtx], run[StatKeyword.recovered],run[StatKeyword.rescued], run[StatKeyword.skipNoKey], \
												run[StatKeyword.skippedIncompleteDel], run[StatKeyword.skippedIncompleteKey], run[StatKeyword.skippedBadGop],run[StatKeyword.acquiredNum])

#******************************************************************************
def usage():
	print "usage: "+sys.argv[0]+" -f<tests_folder> [-r]"
	sys.exit(0)

def main():
	global verbose, printRebufferingsOnly
	try:
		opts, args = getopt.getopt(sys.argv[1:], "vrf:", ["-v", "-r", "test-folder="])
	except getopt.GetoptError as err:
		print str(err)
		usage()
		sys.exit(2)
	for o, a in opts:
		if o in ("-f", "--test-folder"):
			testFolder = a
		elif o in ("-v"):
			verbose = True
		elif o in ("-r"):
			printRebufferingsOnly = True
		else:
			assert False, "unhandled option "+o
	if not 'testFolder' in locals():
		usage();
	run(testFolder)

if __name__ == '__main__':
	main()
