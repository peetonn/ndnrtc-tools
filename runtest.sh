#!/bin/bash

PRODUCER_NAME="clockwork_ndn"
PRODUCER_PREFIX="/ndn/edu/ucla/remap"

NDNCON_APP_DIR="/Users/peetonn/Library/Developer/Xcode/DerivedData/NDN-RTC-avqsddpibbpodvhlerpstaxbmfzi/Build/Products/Debug/ndncon.app"
NDNCON_APP="${NDNCON_APP_DIR}/Contents/MacOS/ndncon"
NDNCON_APP_ARGS="-auto-fetch-prefix ${PRODUCER_PREFIX} -auto-fetch-user ${PRODUCER_NAME} -auto-fetch-audio 1"

NDN_DAEMON=nfd
NDN_DAEMON_START="nfd-start"
NDN_DAEMON_STOP=nfd-stop
NDN_DAEMON_LOG="nfd.log"
NDN_DAEMON_REG_PREFIX="nfdc register"

NDNPING_CMD="ndnping"
PING_CMD="ping"

SCREENCAP_INTERVAL=20
SCREENCAP="screencapture -l$(osascript -e 'tell app "Safari" to id of window 1')"

HOSTS_SCRIPT="gethubs.py"
HOSTS_WEBPAGE="http://www.arl.wustl.edu/~jdd/ndnstatus/ndn_prefix/tbs_ndnx.html"
GET_HOSTS_CMD="python $HOSTS_SCRIPT $HOSTS_WEBPAGE"

HUBS=()
HUB_NAMES=()

TESTS_FOLDER="out/$(date +%Y-%m-%d_%H-%M)"
DEBUG=1

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
	echo "${0} -t <test_time> [-h <hubs_file>]"
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
	# local pid
	# pid=$(getPid "${1}")

	# if [ -n "${pid}" ] ; then
	# 	echo "[***] stopping ${1} (${pid})"	
	# 	kill -9 $pid
	# 	echo "[***] ${1} stopped"
	# fi
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
	$NDN_DAEMON_START &> "$TESTS_FOLDER/$hub/nfd.log"
	
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

	log "setting up ndncon for $hub..."
	$NDNCON_APP $NDNCON_APP_ARGS > "$TESTS_FOLDER/$hub/ndncon.log" 2>&1 &
}

function copyNdnconLog()
{
	local hub=$1
	cp /tmp/consumer-${PRODUCER_NAME}-*.log $TESTS_FOLDER/$hub/
}

function takeScreenshot()
{
	local hub=$1
	$SCREENCAP $TESTS_FOLDER/$hub/$SCREENSHOT_IDX.png
}

function cleanupNdncon()
{
	stopApp "ndncon"
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

hubsFile="N/A"
testTime=""

while getopts ":h:t:" opt; do
  case $opt in
    h) hubsFile="$OPTARG"
    ;;
    t) testTime="$OPTARG"
    ;;
    \?) log "Invalid option -$OPTARG" >&2
    ;;
  esac
done

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
    	takeScreenshot $hub $address
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
