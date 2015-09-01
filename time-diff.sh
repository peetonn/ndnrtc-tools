#!/bin/sh

float_scale=2

function float_eval()
{
    local stat=0
    local result=0.0
    if [[ $# -gt 0 ]]; then
        result=$(echo "scale=$float_scale; $*" | bc -q 2>/dev/null)
        stat=$?
        if [[ $stat -eq 0  &&  -z "$result" ]]; then stat=1; fi
    fi
    echo $result
    return $stat
}

function float_cond()
{
    local cond=0
    if [[ $# -gt 0 ]]; then
        cond=$(echo "$*" | bc -q 2>/dev/null)
        if [[ -z "$cond" ]]; then cond=0; fi
        if [[ "$cond" != 0  &&  "$cond" != 1 ]]; then cond=0; fi
    fi
    local stat=$((cond == 0))
    return $stat
}

i=0

tolerate=7
if [ $# -gt 0 ]; then
	tolerate=$1
fi	

while read line2ts line2rest; do
	if [ $i -ne 0 ]; then
		diff=$(float_eval "${line2ts} - ${line1ts}")
        
        if float_cond "${diff} < 1"; then
            diff=$(float_eval "${diff} * 1000")
        fi

		diffSec=$(float_eval "${diff} / 1000")

		if float_cond "${diff} > ${tolerate}"; then
			echo "\t^ ${diffSec} sec, ${diff} msec"
		fi
		
		echo "${line2ts}\t${line2rest}"
	else
		echo "${line2ts}\t${line2rest}"
	fi
    line1ts=$line2ts
    line1rest="${line2rest}"     
	let i++
done