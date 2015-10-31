#!/bin/sh
export PATH="/usr/local/bin":$PATH

PRODUCER_PREFIX="/a/b/c"
CONSUMER_PREFIX="/a/b/c"

NDNCON_APP_DIR="/ndnproject/ndncon.app"
NDNCON_APP="${NDNCON_APP_DIR}/Contents/MacOS/ndncon"

NDN_DAEMON=nfd
NDN_DAEMON_START="echo remap2015 | ndnsec-unlock-tpm && sudo nfd-start"
NDN_DAEMON_STOP="nfd-stop"
NDN_DAEMON_LOG="nfd.log"
NDN_DAEMON_REG_PREFIX="nfdc register"

NDNPING_CMD="ndnping"
PING_CMD="ping"

SCREENCAP_INTERVAL=10
SCREENCAP="screencapture -l$(osascript -e 'tell app "Safari" to id of window 1')"

HOSTS_SCRIPT="gethubs.py"
HOSTS_WEBPAGE="http://www.arl.wustl.edu/~jdd/ndnstatus/ndn_prefix/tbs_ndnx.html"
GET_HOSTS_CMD="python $HOSTS_SCRIPT $HOSTS_WEBPAGE"

HUBS=()
HUB_NAMES=()

DEBUG=1
hubsFile="N/A"
testTime=""


while getopts ":h:t:vazp:c:o:" opt; do
  case $opt in
    h) hubsFile="$OPTARG"
    ;;
    t) testTime="$OPTARG"
    ;;
    v) TEST="-auto-fetch-video 1 -auto-publish-video 1"
    ;;
    a) TEST="-auto-fetch-audio 1 -auto-publish-audio 1"
    ;;
    z) TEST="-auto-fetch-video 1 -auto-publish-video 1 -auto-fetch-audio 1 -auto-publish-audio 1"
    ;;
    p) PRODUCER_NAME="$OPTARG"
    ;;
    c) CONSUMER_NAME="$OPTARG"
    ;;
    o) OUT_FOLDER="$OPTARG"
    ;;
    \?) log "Invalid option -$OPTARG" >&2
    ;;
  esac
done

TESTS_FOLDER="${OUT_FOLDER}/$(date +%Y-%m-%d_%H-%M)"
NDNCON_APP_ARGS="-auto-publish-prefix ${PRODUCER_PREFIX} -auto-publish-user ${PRODUCER_NAME} -auto-fetch-prefix ${CONSUMER_PREFIX} -auto-fetch-user ${CONSUMER_NAME} $TEST"

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

function usage()
{
	echo "${0} -t <test_time_sec> [-h <hubs_file>]"
	echo "	Test scenario - one-to-one unidirectional stream fetching accross the testbed"
	echo "	It is assumed that theres a producer avaiable somewhere on the testbed under "
	echo "	PRODUCER_PREFIX prefix and PRODUCER_NAME username"
	echo "	This script executes consumer-only tests per hub provided. If hubs file is provided"
	echo "	script will execute one test per hub. Otherwise, it will get all currently available hubs"
	echo "	on NDN testbed and run test per each hub then. A hubs file is a tab-delimited two-column file"
	echo "	first column contains hub name and second its servername or IP address"
	echo "	Each test will run for <test_time_sec> seconds per testbed hub and will include following steps:"
	echo "		- ensure NFD and ndncon are stopped"
	echo "		- start NFD, register prefix / to the current testbed hub"
	echo "		- start ndnping utility"
	echo "		- start ping utility"
	echo "		- start ndncon with auto-fetching arguments to fetch from test producer (test producer is defined"
	echo "			by variables PRODUCER_PREFIX and PRODUCER_NAME"
	echo "		- every 20 seconds a screenshot of opened Safari window will be taken (its supposed to have NDN"
	echo "			testbed map opened in Safari)"
	echo "		- stop ndncon after test time elapsed"
	echo "		- stop NFD, stop ndnping and ping utilities"
	echo "		- copy nfd.log, ndnping.log, ping.log and consumer log file to the subfolder named as currently tested"
	echo "			hub under test run folder in out directory. Test run folder is named with current date and time."
}

function getPid()
{
	local pid
	pid=$(ps -Ao pid,comm | grep "$1" | cut -d' ' -f1)
	echo $pid
}

function stopApp()
{
	killall $1 >/dev/null 2>&1
}

function getHubs()
{
	while read line; do pair=($line); HUB_NAMES+=(${pair[0]}); HUBS+=(${pair[1]}); done < "${1}"
}

function setupEnv()
{
	local hub=$1
	local address=$2

	log "setting up environment for $hub..."
	mkdir -p "$TESTS_FOLDER/$hub"
}

function nfdRegisterPrefix()
{
	local prefix=$1
	local ip=$2

	log "registering prefix / for $ip..."
	eval "${NDN_DAEMON_REG_PREFIX} / udp://$ip"
}

function setupNfd()
{
	local hub=$1
	local address=$2

	log "setting up NFD for $hub..."
	eval $NDN_DAEMON_START &> "$TESTS_FOLDER/$hub/nfd.log"
	
	if [ $? -eq 0 ]; then
		sleep 5
		nfdRegisterPrefix $PRODUCER_PREFIX $address
	fi
}

function setupNdnping()
{
	local hub=$1
	local address=$2

	log "setting up ndnping for $hub..."
	$NDNPING_CMD $PRODUCER_PREFIX > "$TESTS_FOLDER/$hub/ndnping.log" 2>&1 &
}

function setupPing()
{
	local hub=$1
	local address=$2

	log "setting up ping for $hub..."
	$PING_CMD $address > "$TESTS_FOLDER/$hub/ping.log" 2>&1 &
}

function setupNdncon()
{
	local hub=$1
	local address=$2

	log "setting up ndncon for $hub (arguments ${NDNCON_APP_ARGS})..."
	$NDNCON_APP $NDNCON_APP_ARGS > "$TESTS_FOLDER/$hub/ndncon.log" 2>&1 &
}

function copyNdnconLog()
{
	local hub=$1
	mv /ndnrtc-log/consumer-*.log $TESTS_FOLDER/$hub/ 
	#add producer and ndnrtc log save
	mv /ndnrtc-log/producer-*.log $TESTS_FOLDER/$hub/
	mv /ndnrtc-log/ndnrtc.log $TESTS_FOLDER/$hub/
}

function takeScreenshot()
{
	local hub=$1
	$SCREENCAP $TESTS_FOLDER/$hub/$SCREENSHOT_IDX.png
}

function cleanupNdncon()
{
	stopApp "ndncon"
	rm -rf /ndnrtc-log/*
}

function cleanupPing()
{
	stopApp $PING_CMD
}

function cleanupNdnping()
{
	stopApp $NDNPING_CMD
}

function cleanupNfd()
{
	eval "${NDN_DAEMON_STOP}"
}





if [ "${testTime}" = "" ]
then 
	usage
	exit 1
fi

if [ "${hubsFile}" = "N/A" ]
then
	log "retrieveing actual list of hubs..."
	tmpfile=$(mktemp -t ndnhubs)
	eval $GET_HOSTS_CMD > $tmpfile
	getHubs $tmpfile
else
	log "reading hubs from a file..."
	getHubs $hubsFile
fi

# start test run
log "test files will be placed in $TESTS_FOLDER"
mkdir -p "$TESTS_FOLDER"

# make sure everything is down
cleanupNfd
cleanupNdnping
cleanupPing
cleanupNdncon
sleep 2

idx=0

for hub in ${HUB_NAMES[@]} ; do
	address=${HUBS[$idx]}
	log "running test $idx for hub $hub (address $address)"
	
	setupEnv $hub $address
	if [ $? -ne 0 ]; then
        error "error setting up environment for $hub. skipping to the next hub..."
        continue
    fi

	setupNfd $hub $address
	if [ $? -ne 0 ]; then
        error "error setting up NFD for $hub. skipping to the next hub..."
        continue
    fi

	#sleep to start hub nfdc script manually
	log "sleep 15 sec to start hub nfdc script manually"
	sleep 15

    setupNdnping $hub $address
	if [ $? -ne 0 ]; then
        error "error setting up ndnping for $hub. skipping to the next hub..."
        continue
    fi

    setupPing $hub $address
	if [ $? -ne 0 ]; then
        error "error setting up ping for $hub. skipping to the next hub..."
        continue
    fi

    setupNdncon $hub $address
    if [ $? -ne 0 ]; then
        error "error setting up ndncon for $hub. skipping to the next hub..."
        continue
    fi

    log "running test $idx..."
    SCREENSHOT_IDX=0
    runTime=0
    while [ $runTime -le $testTime ] ; do
    	sleep $SCREENCAP_INTERVAL
    	#takeScreenshot $hub $address
    	timestamp=$(date +"%T") #>>$TESTS_FOLDER/$hub/resourceUsage-${PRODUCER_NAME}.log
    	timestamp_unix=$(date +%s)
    	nfd_usage=$(ps -h -p `pgrep nfd | tr "\\n" "," | sed 's/,$//'` -o %cpu,%mem,vsz,rss | awk 'NR>1') #>>$TESTS_FOLDER/$hub/resourceUsage-${PRODUCER_NAME}.log
    	ndncon_usage=$(ps -h -p `pgrep ndncon | tr "\\n" "," | sed 's/,$//'` -o %cpu,%mem,vsz,rss|  awk 'NR>1')
    	echo "timestamp: $timestamp, nfd-usage: $nfd_usage" >> $TESTS_FOLDER/$hub/resourceNFDUsage-${PRODUCER_NAME}.log
    	echo "timestamp: $timestamp, timestamp_unix: $timestamp_unix, ndncon-usage: $ndncon_usage" >> $TESTS_FOLDER/$hub/resourceNdnconUsage-${PRODUCER_NAME}.log
    	let runTime+=$SCREENCAP_INTERVAL
    	let SCREENSHOT_IDX+=1
    done

    copyNdnconLog $hub $address
    cleanupNdncon $hub $address
    cleanupPing $hub $address
    cleanupNdnping $hub $address
    cleanupNfd $hub $address
	let idx+=1

	log "test $idx completed"
	sleep 5
done

