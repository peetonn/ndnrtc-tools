#!/bin/sh
testsfolder=$1

logfiles=$(find $testsfolder -name 'consumer-*.log')
#process allowed
THREAD_NUM=6
#define a pipe of symbol with 9
mkfifo tmppipe
exec 9<>tmppipe
#write the THREAD_NUM as \n
for ((i=0;i<$THREAD_NUM;i++))
do
	echo -ne "\n" 1>&9
done  

for file in $logfiles ; do
	{
    #process control
    read -u 9
    {
       	#echo "begin"
       	folder=$(dirname $file)
       	echo "file $file">> "buf-bug2.log"
       	grepfilename=$(echo "$file" | grep -o "consumer\([-/A-z0-9_]*\)")
       	echo "filename is $grepfilename">> "buf-bug2.log"
       	analyzeCmd='python tracebuf-bug.py -f "${file}" -a -n >> buf-bug2.log'
		#echo "running analysis on $file...."
		eval $analyzeCmd
		#echo "done!"
		echo -ne "\n" 1>&9
	}&
}
done
wait
echo "all done"
rm tmppipe 