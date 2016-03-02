#!/bin/bash
for (( c=1; c<=10; c++ ))
do
   echo "run ndncon_autotest-eth.sh $c times"
   /home/remap/ndncon-autotest/ndnrtc-tools/ndncon_autotest-eth.sh -s tests_setup.txt -t 60
   sleep 10
done
for (( b=1; b<=10; b++ ))
do
	echo "run ndncon_auto-test-eth-latFluctuate.sh $b times"
   /home/remap/ndncon-autotest/ndnrtc-tools/ndncon_auto-test-eth-latFluctuate.sh -s tests_setup-latFluc.txt -t 60
   sleep 10
done