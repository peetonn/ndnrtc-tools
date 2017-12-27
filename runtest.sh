#!/bin/sh

DEBUG=1

RUNTIME=$1
USER_NOTE=$2

REMOTE_SERVER="node"
USER="peter"
OUT_FOLDER=.

NDN_DAEMON=nfd
NDN_DAEMON_START="nfd-start"
NDN_DAEMON_STOP=nfd-stop
NDN_DAEMON_LOG="nfd.log"
NDN_DAEMON_REG_PREFIX="nfdc register"

PRODUCER_PREFIX="/icear"
PRODUCER_IP=131.179.142.116
# PRODUCER_IP=131.179.142.128

NDNRTC_LOCATION="/home/peter/ice-ar/edge/ndnrtc/cpp/peter-build"
NDNRTC_CLIENT="$NDNRTC_LOCATION/ndnrtc-client"
NDNRTC_CONFIG="$NDNRTC_LOCATION/icear-consumer.cfg"
NDNRTC_RULEFILE="$NDNRTC_LOCATION/rule.conf"
NDNRTC_IDENTITY="/"
NDNRTC_RUNTIME=$RUNTIME

function log()
{
	if [ $DEBUG -eq "1" ] ; then
		echo "* ${1}"
	fi
}

function error()
{
	echo "! ${1}"
}

function runCmd()
{
	cmd=$1
	log $cmd
	eval "ssh -t $USER@$REMOTE_SERVER $cmd"
}

function nfdRegisterPrefix()
{
	local prefix=$1
	local ip=$2

	log "registering prefix / for $ip..."
	runCmd "$NDN_DAEMON_REG_PREFIX $prefix udp://$ip"
}

function setupNfd()
{
	local prefix=$1
	local address=$2

	log "setting up NFD..."
	runCmd "$NDN_DAEMON_START"
	
	if [ $? -eq 0 ]; then
		sleep 2
		nfdRegisterPrefix $prefix $address
	fi

	ssh -f $USER@$REMOTE_SERVER "journalctl -u nfd > /tmp/nfd.log"
}

function setupTcpDump()
{
	ssh -f $USER@$REMOTE_SERVER "sudo tcpdump -i eno1 'ether proto 0x8624 || udp port 6363' -w /tmp/tcpdump.pcap"
	ssh -f $USER@$REMOTE_SERVER "sudo ndndump -i eno1  > /tmp/ndndump.log"
}

function cleanupTcpDump()
{
	runCmd "sudo killall tcpdump"
	runCmd "sudo killall ndndump"
}

function cleanupNfd()
{
	runCmd "rm /tmp/nfd*.log"
	runCmd "rm /tmp/consumer*.log"
	runCmd "${NDN_DAEMON_STOP}"
	runCmd "killall journalctl"
}

function runClient()
{
	runCmd "$NDNRTC_CLIENT -c $NDNRTC_CONFIG -s $NDNRTC_IDENTITY -p $NDNRTC_RULEFILE -t $NDNRTC_RUNTIME -v"
}

# restart and setup NFD, and gather NFD logs
cleanupNfd
setupNfd $PRODUCER_PREFIX $PRODUCER_IP
setupTcpDump

# start tcpdump gathering

# start client
runClient

# stop tcpdump
cleanupTcpDump

# creating subfolder for log files
TESTS_FOLDER="${OUT_FOLDER}/test-$(date +%Y-%m-%d_%H-%M)_$USER_NOTE"
mkdir -p $TESTS_FOLDER

# getting ndnrtc-client logs
scp $USER@$REMOTE_SERVER:/tmp/consumer-*.log $TESTS_FOLDER/
scp $USER@$REMOTE_SERVER:/tmp/nfd*.log $TESTS_FOLDER/
mkdir -p $TESTS_FOLDER/stats
scp $USER@$REMOTE_SERVER:/tmp/*.stat $TESTS_FOLDER/stats
scp $USER@$REMOTE_SERVER:/tmp/tcpdump.pcap $TESTS_FOLDER/
scp $USER@$REMOTE_SERVER:/tmp/ndndump.log $TESTS_FOLDER/

# prepping logs
cd $TESTS_FOLDER
cat consumer-*.log | normalize-time.py | toseqno.py - > all.log
cat ndndump.log | normalize-time.py | toseqno.py - > ndndump-norm.log
prep-logs.sh
cd ..