#!/usr/bin/perl

# $txt='faceid=259 remote=ether://[01:00:5e:00:17:aa] local=dev://eth0 counters={in={0i 0d 0B} out={0i 0d 0B}} non-local persistent multi-access';

# $txt=$1;
$txt=$ARGV[0];
#print $txt;

$re1='.*?';	# Non-greedy match on filler
$re2='(\\d+)';	# Integer Number 1

$re=$re1.$re2;
if ($txt =~ m/$re/is)
{
    $int1=$1;
    print "$int1";
}
# print "done";
