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
RUN_BUILD_RESULTS="build_results.py"
RUN_BUILD_SHORT_RESULTS="build_results.py -r"

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
 	local producerHub
 	local consumerHub

	cpIp=$1
	cpUser=$2
	test_time=$3
	test_type=$4
	tests_folder=$5
	producer=$6
	consumer=$7
	scpdest=$8
	producerHub=$9
	consumerHub=$10

	eruntestLog=${tests_folder}/eruntest-${producer}.out
	clientDstLogDir="$test_folder/$producer"
	mkdir -p $clientDstLogDir

	log "starting consumer-producer ${cpIp} (${cpUser}-$producer, fetching from $consumer, test type ${test_type})"
	RUNTEST_CMD="ssh -f ${cpUser}@${cpIp} \"/ndnproject/ndnrtc-tools/eruntest-tb.sh -o /ndnproject/out -t ${test_time} -p ${producer} -c ${consumer} -${test_type} -k ${producerHub} -l${consumerHub}\" &> ${eruntestLog}"
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

	local client1Hub=$1
	local client2Hub=$2
	test_name=$3
	test_time=$4
	test_type=$5
	tests_folder=$6
	
	test_folder="$tests_folder/$test_name"
	mkdir -p $test_folder

	runCp $CPIP2 $CPUSER2 $test_time $test_type $test_folder $NDNCON_USER2 $NDNCON_USER1 $client2Hub $client1Hub
	runCp $CPIP1 $CPUSER1 $test_time $test_type $test_folder $NDNCON_USER1 $NDNCON_USER2 $client1Hub $client2Hub
	sleep 10

	log "running test (logs in ${test_folder})..."
	sleep $test_time
	sleep 15
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
	while read client1Hub client2Hub type; do 
		log "running test $i ($client1Hub <-> $client2Hub)"
		testName="${i}-${client1Hub}-${client2Hub}"
		runtest $client1Hub $client2Hub $testName $testTime $type $TESTS_FOLDER
		
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
	#runCmd "${RUN_BUILD_RESULTS} -f ${TESTS_FOLDER}"
	#runCmd "${RUN_BUILD_SHORT_RESULTS} -f ${TESTS_FOLDER}"
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
