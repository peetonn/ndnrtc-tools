#!/bin/sh
testsfolder=$1

logfiles=$(find $testsfolder -name 'consumer-*.log')
for file in $logfiles ; 
do
	echo "begin"
	folder=$(dirname $file)
	#echo "file is $file"
	grepfilename=$(echo "$file" | grep -o "consumer\([-/A-z0-9_]*\)")
	#echo "file name is $grepfilename"
	analyzeCmd='python analyze.py "${file}" 10 "${folder}/summary-${grepfilename}.txt" --no-headers >> "${folder}/stats-${grepfilename}.log"'
	echo "running analysis on $file...."
	eval $analyzeCmd
	echo "done!"
done
