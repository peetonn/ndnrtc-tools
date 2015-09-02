#!/bin/sh

consumerLog=$1
producerLog=$2
outFolder=$3

echo "retrieveing expressed interests (interests-timed.log)..."
cat $consumerLog | grep "express" | grep "STAT" | time-diff.sh > "${outFolder}/interests-timed.log"

echo "retrieveing received data (data-timed.log)..."
cat $consumerLog | grep "data /" | grep "STAT" | time-diff.sh > "${outFolder}/data-timed.log"

echo "retrieveing rebufferings (rebuf.log)..."
rebuf.py $consumerLog > "${outFolder}/rebuf.log"

echo "retrieveing producer publishing (sent-or-cached.log)..."
cat $producerLog | grep "sent\|added" | time-diff.sh > "${outFolder}/sent-or-cached.log"

echo "retrieveing producer incoming interests (interest-and-sent.log)..."
cat $producerLog | grep "sent\|incoming" | time-diff.sh > "${outFolder}/interest-and-sent.log"

echo "done."