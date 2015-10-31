#!/bin/bash
DEBUG=0


TEST_IFACE="eth0"
CPIP1="192.168.1.111"
CPUSER1="remap"
CPIP2="192.168.1.222"
CPUSER2="remap"

NDNCON_USER1="test3"
NDNCON_USER2="test4"

RUN_ANALYSIS_CMD="analyze.sh"
#RUN_BUILD_RESULTS="build_results.py"
#RUN_BUILD_SHORT_RESULTS="build_results.py -r"

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
	echo "	'a' (audio) 'v' (video) or 'z' (audio+video). Script will run "
	echo "	one test per line by shaping network according to the parameters"
	echo "	specified."
}

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
	producerHub=$8
	consumerHub=$9

	eruntestLog=${tests_folder}/eruntest-${producer}.out
	clientDstLogDir="$test_folder/$producer"
	
	CLIENT_ERUNLOG_ARR+=("$eruntestLog")
	CLIENT_SCP_ARR+=("${cpUser}@${cpIp}")
	CLIENT_DSTLOGDIR_ARR+=("$clientDstLogDir")
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
	

	runCp $CPIP2 $CPUSER2 $test_time $test_type $test_folder $NDNCON_USER2 $NDNCON_USER1 $client2Hub $client1Hub
	runCp $CPIP1 $CPUSER1 $test_time $test_type $test_folder $NDNCON_USER1 $NDNCON_USER2 $client1Hub $client2Hub
	#sleep 10

	log "running test (logs in ${test_folder})..."
	#sleep $test_time
	#sleep 15
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
	
	log "copying log files from ${scpCred}:${srcDir}/ to ${dstDir}"
	runCmd "scp -r ${scpCred}:${srcDir}/* ${dstDir}"
	log "done"
}

function runtests()
{
	local setupFile
	local testTime
	setupFile=$1
	testTime=$2
	TESTS_FOLDER=$3

	#TESTS_FOLDER="out/$(date +%Y-%m-%d_%H-%M)"
	#TESTS_FOLDER="out/2015-10-05_19-50"
	log "test results will be placed in $TESTS_FOLDER"
	

	i=1
	while read client1Hub client2Hub testtype; do 
		log "running test $i ($client1Hub <-> $client2Hub)"
		testName="${i}-${testtype}-${client1Hub}-${client2Hub}"
		runtest $client1Hub $client2Hub $testName $testTime $testtype $TESTS_FOLDER
		
		k=0
		for erunLog in "${CLIENT_ERUNLOG_ARR[@]}" ; do
			clientRemoteLogDir="/"$(cat $erunLog  | grep -e "test files will be placed in \([-/A-z0-9_]*\)" | sed 's/.* \///')
			sleep 0.1
			copyClientLogs "${CLIENT_SCP_ARR[$k]}" "${clientRemoteLogDir}" "${CLIENT_DSTLOGDIR_ARR[$k]}"
			let k=$k+1			
		done
		for erunLogDel in "${CLIENT_ERUNLOG_ARR[@]}" ; do
			CLIENT_ERUNLOG_ARR=(${CLIENT_ERUNLOG_ARR[@]/$CLIENT_ERUNLOG_ARR})
		done
		for CLIENT_SCP_ARRDel in "${CLIENT_SCP_ARR[@]}" ; do
			CLIENT_SCP_ARR=(${CLIENT_SCP_ARR[@]/$CLIENT_SCP_ARRDel})
		done
		for CLIENT_DSTLOGDIR_ARRDel in "${CLIENT_DSTLOGDIR_ARR[@]}" ; do
			CLIENT_DSTLOGDIR_ARR=(${CLIENT_DSTLOGDIR_ARR[@]/$CLIENT_DSTLOGDIR_ARRDel})
		done
		#sleep 1
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

while getopts ":s:t:f:" opt; do
  case $opt in
    s) setupFile="$OPTARG"
    ;;
    t) testTime="$OPTARG"
    ;;
    f) testsfoler="$OPTARG"
    ;;
    \?) log "Invalid option -$OPTARG" >&2
    ;;
  esac
done

if [ $setupFile = "n/a" ]
then
	usage
fi

runtests $setupFile $testTime $testsfoler
