# NDN-RTC debugging/log analyzing cheatsheet

## Useful scripts

* `normalize-time.py` - offsetting all timestamps in the file by subtracting first timestamp
* `time-diff.py` - print out time differences between log lines (pass -t for custom threshold)

## Useful terminal one-liners

### prettify log
Cut out redundant columns(log level, component and object memory address) and normalize time (`awk`):

    cat all.log | normalize-time.py | awk -F'[\t:]'  '{ print $1, $3 }'

### applying regexes
Apply regex to extract specific match from log line (`awk`+`gawk`):

    cat all.log | awk -F'[\t:]' '{ print $1, $3}' | gawk 'match($0, /->\[(.*)\]/, a) { print $1, a[1] }'

Same as above, but replaces states with numbers:
    
    cat all.log | awk -F'[\t:]' '{ print $1, $3}' | gawk 'match($0, /->\[(.*)\]/, a) { print $1, a[1] }' | gawk 'match($2, /(.*)/, a) {tag["Idle"]=1; tag["Bootstrapping"]=2; tag["Adjusting"]=3; tag["Fetching"]=4;}{ print $1, tag[a[1]], a[1] }'

### plot consumer states
Plot sates graph; first 5 minutes (`awk`, `gawk', `gnuplot`):

    cat all.log | awk -F'[\t:]' '{ print $1, $3}' | \
    gawk 'match($0, /->\[(.*)\]/, a) { print $1, a[1] }' | \
    gawk 'match($2, /(.*)/, a) {tag["Idle"]=1; tag["Bootstrapping"]=2; tag["Adjusting"]=3; tag["Fetching"]=4;}{ print $1, tag[a[1]], a[1] }' | \
    gnuplot -p -e 'set xlabel "Time";
                   set ylabel "State";
                   set yrange [0:5];
                   set title "States";
                   plot "<cat" with steps notitle'

### interest-data exchange
Get Interest-Data (for segments 0, no parity) timestamps (columns are: timestamp, delta-interest, delta-data, key-interest, key-data, metadata-interest, metadata-data):

    cat all.log | grep "express\|onData: /" | toseqno.py - | \
        awk -F'[\t:]' '{ print $1, $3, $4, $5, $6}' | \
        gawk -v OFS=',' 'match($0, /(express .*\/d\/([0-9]+)\/%00%00.*)|(\/.*\/d\/([0-9]+)\/%00%00.*)|(express .*\/k\/([0-9]+)\/%00%00.*)|(\/.*\/k\/([0-9]+)\/%00%00.*)|(express .*\/_meta\/%FD%([0-9]+)\/%00%00.*)|(\/.*\/_meta\/%FD%([0-9]+)\/%00%00.*)/, a) { print $1, a[2], a[4], a[6], a[8], a[10], a[12] }'

Plot scatter graph for the above data (not useful with all data):
    
    cat all.log | grep "express\|onData: /" | toseqno.py - | \
        awk -F'[\t:]' '{ print $1, $3, $4, $5, $6}' | \
        gawk -v OFS=',' 'match($0, /(express .*\/d\/([0-9]+)\/%00%00.*)|(\/.*\/d\/([0-9]+)\/%00%00.*)|(express .*\/k\/([0-9]+)\/%00%00.*)|(\/.*\/k\/([0-9]+)\/%00%00.*)|(express .*\/_meta\/%FD%([0-9]+)\/%00%00.*)|(\/.*\/_meta\/%FD%([0-9]+)\/%00%00.*)/, a) { print $1, a[2], a[4], a[6], a[8], a[10], a[12] }' > id.csv && \
        gnuplot -p -e 'set datafile sep ","; 
                       set key outside; 
                       set xlabel "Time"; 
                       set ylabel "Delta frames"; 
                       set y2label "Key frames"; 
                       set ytics nomirror; 
                       set y2tics; 
                       plot "id.csv" using 1:2 title "delta-I", 
                            "" using 1:3 title "delta-D", 
                            "" using 1:4 title "key-I" axes x1y2, 
                            "" using 1:5 title "key-D" axes x1y2, 
                            "" using 1:6 title "meta" axes x1y2,'  

### log slicing

Extract +/-100ms of log entries around 5th minute in the log file:

    cat all.log | chunk.py -i 100 5min

### frames assembling and playout
CSV format: 
    timestamp, interest-seg0-delta, interest-seg0-key, frame-assembled-delta, frame-assembled-key, frame-playout-delta, frame-playout-key
    
    cat 0_log_debug.log | gawk 'match($0, /(requested.*\/(d|k)\/([0-9]+) .*)|(assembled frame.*\/(d|k)\/([0-9]+).*)|(play frame.*\/(d|k)\/([0-9]+).*)/, a) \
                                { OFS=","; \
                                  if (a[2] == "d") \
                                    print $1, a[3], "", "", "", "", ""; \
                                  else { \
                                    if (a[2] == "k") \
                                      print $1, "", a[3], "" , "" , "" , "", ""; \
                                    else { \
                                      if (a[5] == "d") \
                                        print $1, "", "", a[6], "", "", ""; \
                                      else { \
                                        if (a[5] == "k") \
                                          print $1, "", "", "", a[6], "", ""; \
                                        else { \
                                          if (a[8] == "d") \
                                            print $1, "", "", "", "", a[9], ""; \
                                          else { \
                                            if (a[8] == "k") \
                                              print $1, "", "", "", "", "", a[9]; \
                                          }}}}}}' > frames.csv
    gnuplot -p -e 'set datafile sep ","; 
                   set key outside; 
                   set xlabel "Time"; 
                   set ylabel "Delta frames"; 
                   set y2label "Key frames"; 
                   set ytics nomirror; 
                   set y2tics; 
                   plot "frames.csv" using 1:2 title "delta-I", 
                        "" using 1:3 title "key-I" axes x1y2, 
                        "" using 1:4 title "delta-Assembled", 
                        "" using 1:5 title "key-Assembled" axes x1y2, 
                        "" using 1:6 title "delta-play",
                        "" using 1:7 title "key-play" axes x1y2,'



