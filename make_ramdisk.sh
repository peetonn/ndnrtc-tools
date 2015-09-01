#/bin/sh
umount /Volumes/ramdisk
diskutil erasevolume HFS+ 'ramdisk' `hdiutil attach -nomount ram://2097152`
mkdir -p /Volumes/ramdisk/ndnconlog
sudo rm /ndnrtc-log
sudo ln -s /Volumes/ramdisk/ndnconlog /ndnrtc-log