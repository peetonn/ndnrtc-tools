#!/bin/sh
rm -Rf /ndnproject/ndncon.app
cp -Rv ~/ndncon-autotest-remote/ndncon.app /ndnproject
chmod +x /ndnproject/ndncon.app/Contents/MacOS/ndncon
