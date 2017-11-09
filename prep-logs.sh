#!/bin/sh

cat all.log | grep -v "TRACE" > debug.log
cat all.log | grep "\-\-■" > pqueue.log
cat debug.log | grep "state-machine\|buffer]" > buffer.log
cat debug.log | grep "state-machine\|buffer]\|\-\-■" > buffer-pq.log
cat debug.log | grep "state-machine\|buffer]\|\-\-■\|DRD" > buffer-pq-drd.log
cat all.log | grep "interest-control" > ic.log
cat all.log | grep "added segment" > buffer-control.log
cat all.log | grep "state-machine" > states.log
cat nfd-raw.log | colrm 1 35 > nfd.log
cat nfd-raw.log | colrm 1 35 |  toseqno.py - > nfd-seq.log
#cat nfd-ndnrtc.log | colrm 19 74 | time-diff.py > nfd-ndnrtc-td.log
#cp /tmp/nfd.log .
#cp /tmp/loop-producer.log .