#!/usr/bin/env python

#like -f /Users/remap/ndnrtc-tools/2015-09-08_13-33/7-v-lat100000loss0bw200000/test1/hub1469c/window.log
import numpy as np
from collections import deque
import pylab as plt
import sys
import getopt
import os


def run(testFolder):
	#windowA/B size
	N = 10
	windowA=deque(maxlen=N)
	windowB=deque(maxlen=N)

	avgA = []
	avgB = []
	deltaArr = []

	with open(testFolder, 'r') as f:
	  f.readline() # skip header
	  for line in f:
	    arr=line.split()
	    if len(arr)>1:
	      delta = float(arr[1])
	      deltaArr.append(delta)
	      #print delta
	      windowB.append(delta)
	      windowA.append(windowB[0])
	      # I'll store the averages so we can plot them, but you can just use
	      # avgA/avgB as a metric for stability, without storing a history.
	      avgA.append(np.sum(windowA)/len(windowA))
	      avgB.append(np.sum(windowB)/len(windowB))

	# Plot the result:
	avgA = np.array(avgA)
	avgB = np.array(avgB)
	plt.figure()
	# plt.plot(avgA-avgB)
	# Or equally telling:
	plt.plot(avgA/avgB,'bo-')
	#threshold empirical
	plt.plot([0,len(avgA)],[0.7,0.7])
	plt.plot([0,len(avgA)],[1.3,1.3])
	#plt.plot(deltaArr)
	plt.show()

def usage():
	print "usage: "+sys.argv[0]+" -f<tests_folder>, draw delta window graph"
	sys.exit(0)

def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], "f:", ["test-folder="])
	except getopt.GetoptError as err:
		print str(err)
		usage()
		sys.exit(2)
	for o, a in opts:
		if o in ("-f", "--test-folder"):
			testFolder = a
		else:
			assert False, "unhandled option "+o
	if not 'testFolder' in locals():
		usage();
	run(testFolder)

if __name__ == '__main__':
	main()
