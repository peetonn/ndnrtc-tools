#!/usr/bin/env python

import getopt
import sys
from subprocess import call

nlcPrefPath = "/Users/peetonn/Library/Preferences/com.apple.network.prefPaneSimulate.plist"

nlcParams = [ {"lat":50}, {"lat":100}, {"lat":150}, {"lat":200}, {"lat":250},\
{"loss":0.1}, {"loss":0.5}, {"loss":1}, {"loss":1.5}, {"loss":2}, {"loss":2.5} ]
nlcProfileTemplate = "{{ DNSDelayValue = 0; DownlinkBandwidth = {2}; DownlinkBandwidthUnit = 0; DownlinkDelay = {0}; DownlinkPacketLossRatio = {1}; ExcludeLoopback = 1; ProtocolFamily = 0; RunOnInterface = All; UplinkBandwidth = {2}; UplinkBandwidthUnit = 0; UplinkDelay = {0}; UplinkPacketLossRatio = 0; }}"

def usage():
	print "usage: "+sys.argv[0]+" -<s (setup)|r (reset) |a (active=profile_name)>"
	sys.exit(0)

def setupNlc():
	for param in nlcParams:
		lat = param["lat"] if "lat" in param.keys() else 0
		loss = param["loss"] if "loss" in param.keys() else 0
		bw = param["bw"] if "bw" in param.keys() else 0
		profile = nlcProfileTemplate.format(lat, loss, bw)
		profileName = "lat{0}loss{1}bw{2}".format(lat, loss, bw)
		call(["defaults", "write", nlcPrefPath, "Profiles", "-dict-add", profileName, profile])
		print "added profile "+profileName

def clearNlc():
	print "resetting Network Link Conditioner..."
	call(["defaults", "delete", nlcPrefPath])

def setActiveProfile(profileName):
	print "setting profile "+profileName
	call(["defaults", "write", nlcPrefPath, "SelectedProfile", profileName])

def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], "sra:", ["setup", "reset", "active="])
	except getopt.GetoptError as err:
		print str(err)
		usage()
		sys.exit(2)
	if len(opts) == 0:
		usage()
		sys.exit(2)
	for o, a in opts:
		if o in ("-s", "--setup"):
			setupNlc()
		elif o in ("-r", "--reset"):
			clearNlc()
		elif o in ("-a", "--active"):
			setActiveProfile(a)
		else:
			assert False, "unhandled option "+o
	print "done"

if __name__ == '__main__':
	main()

