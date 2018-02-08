#!/bin/sh

LOG_ALL="all.log"
LOG_ALL_NO_BUFFER_JUNK="0_log_all_buff_clean.log.tmp"
LOG_DEBUG="0_log_debug.log"
LOG_INFO="0_log_info.log"
LOG_WARN="0_log_warn.log"
LOG_STATES="1_states.log"
LOG_BUFFER="2_buffer.log"
LOG_BUFFER_CONTROL="2_buffer_control.log"
PQUEUE_DUMP="3_pqueue_dump.log"
LOG_PLAY_QUEUE="3_playout_queue.log"
LOG_PLAY_QUEUE_DRD="3_playout_queue_drd.log"
LOG_INTEREST_CONTROL="4_interest_control.log"

slice=$1

function plotStates()
{
	cat $LOG_STATES | awk -F'[\t:]' '{ print $1, $3}' | \
		gawk 'match($0, /->\[(.*)\]/, a) {tag["Idle"]=1; tag["WaitForRightmost"]=2; tag["WaitForInitial"]=3; tag["Chasing"]=4; tag["Adjusting"]=5; tag["Fetching"]=6;}{ print $1, tag[a[1]], a[1] }' | \
		gnuplot -p -e 'set terminal png; set xlabel "Time"; set ylabel "State"; set yrange [0:6]; set title "States"; plot "<cat" with steps notitle' > states.png
	
	cat $LOG_STATES | awk -F'[\t:]' '{ print $1, $3}' | \
		gawk 'match($0, /->\[(.*)\]/, a) {tag["Idle"]=1; tag["WaitForRightmost"]=2; tag["WaitForInitial"]=3; tag["Chasing"]=4; tag["Adjusting"]=5; tag["Fetching"]=6;}{ print $1, tag[a[1]], a[1] }' | \
		gnuplot -p -e 'set xlabel "Time"; set ylabel "State"; set yrange [0:6]; set title "States"; plot "<cat" with steps notitle'
}

function runPlots()
{
	# plotting interest-data exchange
	# cat $LOG_ALL | grep "express.*%00%00\|received data /" | toseqno.py - | grep -v "parity" | \
	# 	awk -F'[\t:]' '{ print $1, $3, $4}' | grep "vp9/d" | gawk -v OFS=',' 'match($0, /.*((received data .*\/([0-9]+)\/%00%00.*)|(express .*\/([0-9]+)\/%00%00.*))/, a) { print $1, a[3], a[5] }' > di.csv && \
	# 	gnuplot -p -e 'set terminal png size 1000,500; set datafile sep ","; set key outside; plot "di.csv" using 1:2 title "Data", "" using 1:3 title "Interests"' > id.png
	cat $LOG_ALL | grep "express.*\|received data /" | toseqno.py - | \
		awk -F'[\t:]' '{ print $1, $3, $4, $5, $6}' | \
		gawk -v OFS=',' 'match($0, /.*((received data .*d\/([0-9]+)\/%.*)|(express .*d\/([0-9]+)\/%.*)|(received data .*k\/([0-9]+)\/%.*)|(express .*k\/([0-9]+)\/%.*)|(express .*k exclude.*,([0-9]+).*))/, a) { print $1, a[3], a[5], a[7], a[9], a[11] }' > di.csv && \
		gnuplot -p -e 'set terminal png size 1000,500; 
					   set datafile sep ","; 
					   set key outside; 
					   set xlabel "Time"; 
					   set ylabel "Delta frames"; 
					   set y2label "Key frames"; 
					   set ytics nomirror; 
					   set y2tics; 
					   plot "di.csv" using 1:2 title "delta-D", 
					   		"" using 1:3 title "delta-I", 
					   		"" using 1:4 title "key-D" axes x1y2, 
					   		"" using 1:5 title "key-I" axes x1y2, 
					   		"" using 1:6 title "key-RM" axes x1y2,'  > id.png

	if [ -f ndndump-norm.log ]; then
		# plotting interest-data exchange from ndndump
		cat ndndump-norm.log |  gawk -v OFS=',' 'match($0, /.*((DATA:.*d\/([0-9]+)\/%.*)|(INTEREST: .*d\/([0-9]+)\/%.*)|(DATA:.*k\/([0-9]+)\/%.*)|(INTEREST: .*k\/([0-9]+)\/%.*)|(INTEREST: .*k.*Exclude=.*,([0-9]+).*))/, a) { print $1, a[3], a[5], a[7], a[9], a[11] }' > di-nfd.csv && \
			gnuplot -p -e 'set terminal png size 1000,500; 
						   set datafile sep ","; 
						   set key outside; 
						   set xlabel "Time"; 
						   set ylabel "Delta frames"; 
						   set y2label "Key frames"; 
						   set ytics nomirror; 
						   set y2tics; 
						   plot "di-nfd.csv" using 1:2 title "delta-D", 
						   		"" using 1:3 title "delta-I", 
						   		"" using 1:4 title "key-D" axes x1y2, 
						   		"" using 1:5 title "key-I" axes x1y2, 
						   		"" using 1:6 title "key-RM" axes x1y2,'  > id-nfd.png
	fi
}

LOGS=`find . -name "*.log"`
STATS=`find . -name "*.stat"`

mkdir logs-original stats-original
for f in $LOGS; do cp $f logs-original; done;
for f in $STATS; do cp $f stats-original; done;

if [ -z "$slice" ]; then
	cat consumer-*.log | normalize-time.py | toseqno.py - > $LOG_ALL
	if [ -f ndndump.log ]; then
		cat ndndump.log | normalize-time.py | toseqno.py - > ndndump-norm.log
	fi
fi

cat $LOG_ALL | grep -v "\d \[" > $LOG_ALL_NO_BUFFER_JUNK
cat $LOG_ALL_NO_BUFFER_JUNK | grep -v "TRACE" > $LOG_DEBUG
cat $LOG_DEBUG | grep -v "DEBUG" > $LOG_INFO
cat $LOG_INFO | grep -v "INFO" > $LOG_WARN
cat $LOG_DEBUG | grep "state-machine\|buffer]" > $LOG_BUFFER
cat $LOG_ALL | grep "state-machine\|pqueue].*dump" > $PQUEUE_DUMP
cat $LOG_ALL | grep "\-\-■" > $LOG_PLAY_QUEUE
cat $LOG_DEBUG | grep "state-machine\|buffer]\|\-\-■\|DRD" > $LOG_PLAY_QUEUE_DRD
cat $LOG_ALL | grep "interest-control" > $LOG_INTEREST_CONTROL
cat $LOG_ALL | grep "added segment" > $LOG_BUFFER_CONTROL
cat $LOG_ALL | grep "state-machine" > $LOG_STATES

rm $LOG_ALL_NO_BUFFER_JUNK

if [ -z "$slice" ]; then
	if [ -f nfd.log ]; then 
		cat nfd.log | awk -F']: ' ' { print $2} ' | toseqno.py - > nfd-pretty.log
	fi
fi

if [ -z "$slice" ]; then
	plotStates
	sliceSize=100 # frames
	starvationFrames=`cat $LOG_ALL | countframe.py --trigger="Starvation"`
	for fno in $starvationFrames; do 
		sliceDir="slice-${fno}-$sliceSize"
		echo "slicing out log around starvation frame $fno into $sliceDir"
		mkdir -p $sliceDir
		cat $LOG_ALL | chunkbyfno.py -i $sliceSize $fno > $sliceDir/$LOG_ALL
		if [ -f nfd-pretty.log ]; then
			cat nfd-pretty.log | chunkbyfno.py -i $sliceSize $fno > $sliceDir/nfd-pretty.log
		fi
		if [ -f ndndump-norm.log ]; then
			cat ndndump-norm.log | chunkbyfno.py -i $sliceSize $fno > $sliceDir/ndndump-norm.log
		fi
		cd $sliceDir
		prep-logs.sh NOSLICE
		runPlots
		cd ..
	done;

	# cleanup
	for f in $LOGS; do rm $f; done;
	for f in $STATS; do rm $f; done;
fi

#cat nfd-ndnrtc.log | colrm 19 74 | time-diff.py > nfd-ndnrtc-td.log
#cp /tmp/nfd.log .
#cp /tmp/loop-producer.log .