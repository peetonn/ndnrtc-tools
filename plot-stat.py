#!/usr/bin/env python

#like plot-stat.py -f /Users/remap/ndnrtc-tools/2015-09-09_18-45/15-z-lat250000loss0bw200000/test1/hub1469c/run0.stat
#timestamp	new state	buf est	buf tar	buf play	rtt est	D arr	lambda d
import numpy as np
#import matplotlib
from collections import deque
import pylab as plt
import sys
import getopt
import os


def run(statFile):
	tsArr = []
	bufestArr = []
	buftarArr = []
	bufplayArr=[]
	rttestArr=[]
	DarrArr=[]
	lambdadArr=[]
	#lineArr =[][]
	with open(statFile, 'r') as f:
		header=f.readline() # read header
		headerArr=header.split('\t')
		headerArr.pop()# remove '\n'

		for line in f:
			arr=line.split('\t')
			#print arr
			ts=float(arr[0]) if arr[0]!='' else 0.0
			bufest=float(arr[2]) if arr[2]!='' else 0.0
			buftar=float(arr[3]) if arr[3]!='' else 0.0
			bufplay=float(arr[4]) if arr[4]!='' else 0.0
			rttest=float(arr[5]) if arr[5]!='' else 0.0
			Darr=float(arr[6]) if arr[6]!='' else 0.0
			lambdad=float(arr[7]) if arr[7]!='' else 0.0
			tsArr.append(ts)
			bufestArr.append(bufest)
			buftarArr.append(buftar)
			bufplayArr.append(bufplay)
			rttestArr.append(rttest)
			DarrArr.append(Darr)
			lambdadArr.append(lambdad)
		#print tsArr
		#print buftarArr

	headerArr.pop(1)
	headerArr.pop(0)
	print bufestArr
	plt.plot(tsArr,bufestArr, 'bo-',  linewidth=0.5, label="bufestArr")
	plt.plot(tsArr,buftarArr, 'go-',  linewidth=0.5, label="buftarArr")
	plt.plot(tsArr,bufplayArr, 'ro-',  linewidth=0.5, label="buftarArr")
	plt.plot(tsArr,rttestArr, 'yo-',  linewidth=0.5, label="buftarArr")
	plt.plot(tsArr,DarrArr, 'co-',  linewidth=0.5, label="buftarArr")
	plt.plot(tsArr,lambdadArr, 'mo-',  linewidth=0.5, label="buftarArr")
	plt.legend(headerArr)
	plt.ticklabel_format(style='plain', axis='x')
	plt.ticklabel_format(useOffset=False)
	plt.show()

def usage():
	print "usage: "+sys.argv[0]+" -f<tests_folder>, draw delta window graph"
	sys.exit(0)

def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], "f:", ["stat-file="])
	except getopt.GetoptError as err:
		print str(err)
		usage()
		sys.exit(2)
	for o, a in opts:
		if o in ("-f", "--stat-file"):
			statFile = a
		else:
			assert False, "unhandled option "+o
	if not 'statFile' in locals():
		usage();
	run(statFile)

if __name__ == '__main__':
	main()
