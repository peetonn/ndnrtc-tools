# NDN-RTC debugging/log analyzing cheatsheet

## Useful scripts

* `normalize-time.py` - offsetting all timestamps in the file by subtracting first timestamp
* `time-diff.py` - print out time differences between log lines (pass -t for custom threshold)

## Useful terminal one-liners

1. Cut out status, component and object memory address from the log file (`awk`):

    `cat all.log | grep "Starvation" | normalize-time.py | awk -F'[\t:]'  '{ print $1, $3 }'`
    
2. Apply regex to extract specific match from log line (`awk`+`gawk`):
    
    `cat states.log | awk -F'[\t:]' '{ print $1, $3}' | gawk 'match($0, /->\[(.*)\]/, a) { print $1, a[1] }'`

    > Same as above, but replaces states with numbers:
    >
    >   `cat states.log | awk -F'[\t:]' '{ print $1, $3}' | gawk 'match($0, /->\[(.*)\]/, a) {tag["Idle"]=1; tag["WaitForRightmost"]=2; tag["WaitForInitial"]=3; tag["Chasing"]=4; tag["Adjusting"]=5; tag["Fetching"]=6;}{ print $1, tag[a[1]], a[1] }'`

3. Plot sates graph; first 5 minutes (`awk`, `gawk', `gnuplot`):

    `cat states.log | awk -F'[\t:]' '{ print $1, $3}' | gawk 'match($0, /->\[(.*)\]/, a) {tag["Idle"]=1; tag["WaitForRightmost"]=2; tag["WaitForInitial"]=3; tag["Chasing"]=4; tag["Adjusting"]=5; tag["Fetching"]=6;}{ print $1, tag[a[1]], a[1] }' | gnuplot -p -e ' set xlabel "Time"; set ylabel "State"; set yrange [0:6]; set xrange[0:300000]; set title "States"; plot "<cat" with steps notitle'`

