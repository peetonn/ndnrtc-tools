#!/bin/sh

NDNCON_APP_DIR="/ndnproject/ndncon.app"
NDNCON_APP="${NDNCON_APP_DIR}/Contents/MacOS/ndncon"

while true ; do
    	sleep 10
    	ps cax | grep "ndncon" > /dev/null
		if [ $? -eq 0 ]; then
 	 		echo "ndncon is running."
		else
  			eval $NDNCON_APP
		fi
    done