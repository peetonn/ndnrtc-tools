# NDN-RTC debugging/log analyzing cheatsheet

## Useful scripts

* `normalize-time.py` - offsetting all timestamps in the file by subtracting first timestamp
* `time-diff.py` - print out time differences between log lines (pass -t for custom threshold)

## Useful terminal one-liners

1. Cut out status, component and object memory address from the log file (`awk`):

    ```
    cat all.log | grep "Starvation" | normalize-time.py | awk -F'[\t:]'  '{ print $1, $3 }'
    ```
    
2. Apply regex to extract specific match from log line (`awk`+`gawk`):
    
    ```
    cat states.log | awk -F'[\t:]' '{ print $1, $3}' | gawk 'match($0, /->\[(.*)\]/, a) { print $1, a[1] }'
    ```

     Same as above, but replaces states with numbers:
    
      ```
      cat states.log | awk -F'[\t:]' '{ print $1, $3}' | gawk 'match($0, /->\[(.*)\]/, a) {tag["Idle"]=1; tag["WaitForRightmost"]=2; tag["WaitForInitial"]=3; tag["Chasing"]=4; tag["Adjusting"]=5; tag["Fetching"]=6;}{ print $1, tag[a[1]], a[1] }'
      ```

3. Plot sates graph; first 5 minutes (`awk`, `gawk', `gnuplot`):

    ```
    cat states.log | awk -F'[\t:]' '{ print $1, $3}' | gawk 'match($0, /->\[(.*)\]/, a) {tag["Idle"]=1; tag["WaitForRightmost"]=2; tag["WaitForInitial"]=3; tag["Chasing"]=4; tag["Adjusting"]=5; tag["Fetching"]=6;}{ print $1, tag[a[1]], a[1] }' | gnuplot -p -e ' set xlabel "Time"; set ylabel "State"; set yrange [0:6]; set xrange[0:300000]; set title "States"; plot "<cat" with steps notitle'
    ```

4. Get Interest-Data timestamps (first column is data):

    ```
    cat all.log | grep "express.*%00%00\|received data /" | toseqno.py - | grep -v "parity" | awk -F'[\t:]' '{ print $1, $3, $4}' | grep "vp9/d" | gawk -v OFS='\t' 'match($0, /.*((received data .*\/([0-9]+)\/%00%00.*)|(express .*\/([0-9]+)\/%00%00.*))/, a) { print $1, a[3], a[5] }'
    ```

     Plot Interest-Data exchange scatter graph (not useful with all data):
    
    ```
    cat all.log | grep "express.*%00%00\|received data /" | toseqno.py - | grep -v "parity" | awk -F'[\t:]' '{ print $1, $3, $4}' | grep "vp9/d" | gawk -v OFS=',' 'match($0, /.*((received data .*\/([0-9]+)\/%00%00.*)|(express .*\/([0-9]+)\/%00%00.*))/, a) { print $1, a[3], a[5] }' > di.csv && gnuplot -p -e 'set datafile sep ","; set key outside; plot "di.csv" using 1:2 title "Data", "" using 1:3 title "Interests"'
    ```

5. Extract +/-100ms of log entries around 5th minute in the log file:

    ```
    cat all.log | chunk.py -i 100 5min
    ```

