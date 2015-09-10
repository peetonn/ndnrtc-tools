#!/bin/bash
DEBUG=0

PREFIX="/a/b/c"
TEST_IFACE="eth1"
CPIP1="131.179.142.30"
CPUSER1="remap"
CPIP2="131.179.142.33"
CPUSER2="remap"

NDNCON_USER1="test1"
NDNCON_USER2="test2"

NDN_DAEMON=nfd
NDN_DAEMON_START=nfd-start
NDN_DAEMON_STOP=nfd-stop
NDN_DAEMON_LOG="nfd.log"
NDN_DAEMON_REG_PREFIX="nfdc register"

RUN_ANALYSIS_CMD="analyze.sh"

function log()
{
	#if [ $DEBUG -eq "1" ] ; then
		echo "* ${1}"
	#fi
}

function runCmd()
{
	local cmd

	cmd=$1
	if [ $DEBUG -eq "1" ]; then
		echo $cmd
	else
		eval $cmd
	fi
}

function error()
{
	echo "! ${1}"
}

function usage()
{
	echo "${0} -s <tests_setup_file> -t <test_time>"
	echo "	test_time - time of one test in seconds"
	echo "	tests_setup_file - textual tab-delimited file with four columns: "
	echo "	latency, loss, bandwidth and test type. Test type can be either"
	echo "	'a' (audio) 'v' (video) or 'av' (audio+video). Script will run "
	echo "	one test per line by shaping network according to the parameters"
	echo "	specified."
}

function stopApp()
{
	runCmd "killall $1 >/dev/null 2>&1"
}

function nfdRegisterPrefix()
{
	local prefix=$1
	local ip=$2

	log "registering prefix / for $ip..."
	runCmd "${NDN_DAEMON_REG_PREFIX} / udp://$ip"
}

function setupNfd()
{
	local test_folder
	test_folder=$1

	log "setting up NFD..."
	runCmd "$NDN_DAEMON_START &> \"${test_folder}/nfd.log\""
}

function cleanupNfd()
{
	runCmd "${NDN_DAEMON_STOP}"
}

################################################################################
function shapeNetwork()
{
	local lat
	local loss
	local bw
	lat=$1
	loss=$2
	bw=$3

	log "shaping network: latency ${lat}ms, packet loss ${loss}%, bandwidth ${bw}Kbit/s"
	SHAPE_NW_CMD="sudo tc qdisc add dev ${TEST_IFACE} root netem delay ${lat} loss ${loss}"
	runCmd "${SHAPE_NW_CMD}"
}

function unshapeNetwork()
{
	UNSHAPE_NW_CMD="sudo tc qdisc del dev ${TEST_IFACE} root netem"
	runCmd "${UNSHAPE_NW_CMD}"
}

################################################################################
CLIENT_ERUNLOG_ARR=()
CLIENT_DSTLOGDIR_ARR=()
CLIENT_SCP_ARR=()

function runCp()
{
	local tests_folder
	local test_time
	local test_type
	local cpIp
	local cpUser
        local producer
        local consumer
        local scpdest

	cpIp=$1
	cpUser=$2
	test_time=$3
	test_type=$4
	tests_folder=$5
        producer=$6
        consumer=$7
        scpdest=$8
	eruntestLog=${tests_folder}/eruntest-${producer}.out
	clientDstLogDir="$test_folder/$producer"
	mkdir -p $clientDstLogDir

	log "starting consumer-producer ${cpIp} (${cpUser}-$producer, fetching from $consumer, test type ${test_type})"
	RUNTEST_CMD="ssh -f ${cpUser}@${cpIp} \"/ndnproject/ndnrtc-tools/eruntest.sh -o /ndnproject/out -t ${test_time} -h /ndnproject/ndnrtc-tools/hubfile -p ${producer} -c ${consumer} -${test_type}\" &> ${eruntestLog}"
	runCmd "${RUNTEST_CMD}"
	log "logs are in ${eruntestLog}"

	CLIENT_ERUNLOG_ARR+=("$eruntestLog")
	CLIENT_SCP_ARR+=("${cpUser}@${cpIp}")
	CLIENT_DSTLOGDIR_ARR+=("$clientDstLogDir")
}

function runHub()
{
	local test_folder
	test_folder=$1
	runCmd "ndnpingserver $PREFIX & > /dev/null"
	log "ndnpingserver started"
	nfdRegisterPrefix "/" $CPIP1
	nfdRegisterPrefix "/" $CPIP2
}

function cleanupHub()
{
	cleanupNfd
	stopApp ndnpingserver
}

function runtest()
{
	local tests_folder
	local test_time
	local test_type

	test_name=$1
	test_time=$2
	test_type=$3
	tests_folder=$4
	
	test_folder="$tests_folder/$test_name"
	mkdir -p $test_folder

	setupNfd $test_folder
	runCp $CPIP2 $CPUSER2 $test_time $test_type $test_folder $NDNCON_USER2 $NDNCON_USER1
	runCp $CPIP1 $CPUSER1 $test_time $test_type $test_folder $NDNCON_USER1 $NDNCON_USER2
	sleep 10
	runHub $test_folder

	log "running test (logs in ${test_folder})..."
	sleep $test_time
	sleep 15
	cleanupHub
	sleep 5
	log "test completed."
}

function copyClientLogs()
{
	local scpCred
	local srcDir
	local dstDir
	scpCred=$1
	srcDir=$2
	dstDir=$3
	
	log "copying log files from ${scpCred}:${srcDir}/* to ${dstDir}"
	runCmd "scp -r ${scpCred}:${srcDir}/* ${dstDir}"
	log "done"
}

function runtests()
{
	local setupFile
	local testTime
	setupFile=$1
	testTime=$2

	TESTS_FOLDER="out/$(date +%Y-%m-%d_%H-%M)"
	log "test results will be placed in $TESTS_FOLDER"
	mkdir -p "$TESTS_FOLDER"

	i=1
	while read lat loss bw type; do 
		log "running test $i (LATENCY: $lat LOSS: $loss BW: $bw TYPE: $type)"
		shapeNetwork $lat $loss $bw
		testName="${i}-${type}-lat${lat}loss${loss}bw${bw}"
		runtest $testName $testTime $type $TESTS_FOLDER
		unshapeNetwork
		
		k=0
		for erunLog in "${CLIENT_ERUNLOG_ARR[@]}" ; do
			clientRemoteLogDir="/"$(cat $erunLog  | grep -e "test files will be placed in \([-/A-z0-9_]*\)" | sed 's/.* \///')
			copyClientLogs "${CLIENT_SCP_ARR[$k]}" "${clientRemoteLogDir}" "${CLIENT_DSTLOGDIR_ARR[$k]}"
			let k=$k+1			
		done
		sleep 2
		let i=$i+1
	done <$setupFile

	log "invoking analysis on all test results..."
	runCmd "${RUN_ANALYSIS_CMD} ${TESTS_FOLDER}"
}


################################################################################
setupFile="n/a"
testTime=0

while getopts ":s:t:" opt; do
  case $opt in
    s) setupFile="$OPTARG"
    ;;
    t) testTime="$OPTARG"
    ;;
    \?) log "Invalid option -$OPTARG" >&2
    ;;
  esac
done

if [ $setupFile = "n/a" ]
then
	usage
fi

runtests $setupFile $testTime
