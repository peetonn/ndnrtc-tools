#!/bin/sh
testsfolder=$1

logfiles=$(find $testsfolder -name 'consumer-*.log')
for file in $logfiles ; 
do
	folder=$(dirname $file)
	analyzeCmd='python analyze.py "${file}" 10 "${folder}/summary.txt" --no-headers >> "${folder}/stats.log"'
	echo "running analysis on $file...."
	eval $analyzeCmd
	echo "done!"
done
