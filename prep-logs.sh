#!/bin/sh

slice=$1

function plotStates()
{
	cat states.log | awk -F'[\t:]' '{ print $1, $3}' | \
		gawk 'match($0, /->\[(.*)\]/, a) {tag["Idle"]=1; tag["WaitForRightmost"]=2; tag["WaitForInitial"]=3; tag["Chasing"]=4; tag["Adjusting"]=5; tag["Fetching"]=6;}{ print $1, tag[a[1]], a[1] }' | \
		gnuplot -p -e 'set terminal png; set xlabel "Time"; set ylabel "State"; set yrange [0:6]; set title "States"; plot "<cat" with steps notitle' > states.png
	
	cat states.log | awk -F'[\t:]' '{ print $1, $3}' | \
		gawk 'match($0, /->\[(.*)\]/, a) {tag["Idle"]=1; tag["WaitForRightmost"]=2; tag["WaitForInitial"]=3; tag["Chasing"]=4; tag["Adjusting"]=5; tag["Fetching"]=6;}{ print $1, tag[a[1]], a[1] }' | \
		gnuplot -p -e 'set xlabel "Time"; set ylabel "State"; set yrange [0:6]; set title "States"; plot "<cat" with steps notitle'
}

function runPlots()
{
	# plotting interest-data exchange
	# cat all.log | grep "express.*%00%00\|received data /" | toseqno.py - | grep -v "parity" | \
	# 	awk -F'[\t:]' '{ print $1, $3, $4}' | grep "vp9/d" | gawk -v OFS=',' 'match($0, /.*((received data .*\/([0-9]+)\/%00%00.*)|(express .*\/([0-9]+)\/%00%00.*))/, a) { print $1, a[3], a[5] }' > di.csv && \
	# 	gnuplot -p -e 'set terminal png size 1000,500; set datafile sep ","; set key outside; plot "di.csv" using 1:2 title "Data", "" using 1:3 title "Interests"' > id.png
	cat all.log | grep "express.*\|received data /" | toseqno.py - | \
		awk -F'[\t:]' '{ print $1, $3, $4, $5, $6}' | \
		gawk -v OFS=',' 'match($0, /.*((received data .*d\/([0-9]+)\/%.*)|(express .*d\/([0-9]+)\/%.*)|(received data .*k\/([0-9]+)\/%.*)|(express .*k\/([0-9]+)\/%.*)|(express .*k exclude.*,([0-9]+).*))/, a) { print $1, a[3], a[5], a[7], a[9], a[11] }' > di.csv && \
		gnuplot -p -e 'set terminal png size 1000,500; set datafile sep ","; set key outside; set xlabel "Time"; set ylabel "Delta frames"; set y2label "Key frames"; set ytics nomirror; set y2tics; plot "di.csv" using 1:2 title "delta-D", "" using 1:3 title "delta-I", "" using 1:4 title "key-D" axes x1y2, "" using 1:5 title "key-I" axes x1y2, "" using 1:6 title "key-RM" axes x1y2,'  > id.png

	# plotting interest-data exchange from ndndump
	cat ndndump-norm.log |  gawk -v OFS=',' 'match($0, /.*((DATA:.*d\/([0-9]+)\/%.*)|(INTEREST: .*d\/([0-9]+)\/%.*)|(DATA:.*k\/([0-9]+)\/%.*)|(INTEREST: .*k\/([0-9]+)\/%.*)|(INTEREST: .*k.*Exclude=.*,([0-9]+).*))/, a) { print $1, a[3], a[5], a[7], a[9], a[11] }' > di-nfd.csv && \
		gnuplot -p -e 'set terminal png size 1000,500; set datafile sep ","; set key outside; set xlabel "Time"; set ylabel "Delta frames"; set y2label "Key frames"; set ytics nomirror; set y2tics; plot "di-nfd.csv" using 1:2 title "delta-D", "" using 1:3 title "delta-I", "" using 1:4 title "key-D" axes x1y2, "" using 1:5 title "key-I" axes x1y2, "" using 1:6 title "key-RM" axes x1y2,'  > id-nfd.png
}

cat all.log | grep -v "TRACE" > debug.log
cat all.log | grep "\-\-■" > pqueue.log
cat debug.log | grep "state-machine\|buffer]" > buffer.log
cat debug.log | grep "state-machine\|buffer]\|\-\-■" > buffer-pq.log
cat debug.log | grep "state-machine\|buffer]\|\-\-■\|DRD" > buffer-pq-drd.log
cat all.log | grep "interest-control" > ic.log
cat all.log | grep "added segment" > buffer-control.log
cat all.log | grep "state-machine" > states.log

if [ -z "$slice" ]; then
	cat nfd.log | awk -F']: ' ' { print $2} ' | toseqno.py - > nfd-pretty.log
fi

if [ -z "$slice" ]; then
	plotStates
	sliceSize=100 # frames
	starvationFrames=`cat all.log | countframe.py --trigger="Starvation"`
	for fno in $starvationFrames; do 
		sliceDir="slice-${fno}-$sliceSize"
		echo "slicing out log around starvation frame $fno into $sliceDir"
		mkdir -p $sliceDir
		cat all.log | chunkbyfno.py -i $sliceSize $fno > $sliceDir/all.log
		cat nfd-pretty.log | chunkbyfno.py -i $sliceSize $fno > $sliceDir/nfd-pretty.log
		cat ndndump-norm.log | chunkbyfno.py -i $sliceSize $fno > $sliceDir/ndndump-norm.log
		cd $sliceDir
		prep-logs.sh NOSLICE
		runPlots
		cd ..
	done;
	# sliceSize=5s
	# starvations=`cat states.log | grep "Starvation" | awk -- '{ print $1}'`
	# for ts in $starvations; do 
	# 	sliceDir="slice-${ts}-3s"
	# 	echo "slicing out log around starvation time $ts into $sliceDir"
	# 	mkdir -p $sliceDir
	# 	cat all.log | chunk.py -i $sliceSize $ts > $sliceDir/all.log
	# 	cat nfd-pretty.log | chunk.py -i $sliceSize $ts > $sliceDir/nfd-pretty.log
	# 	cd $sliceDir
	# 	prep-logs.sh NO 
	# 	runPlots
	# 	cd ..
	# done;
fi

#cat nfd-ndnrtc.log | colrm 19 74 | time-diff.py > nfd-ndnrtc-td.log
#cp /tmp/nfd.log .
#cp /tmp/loop-producer.log .