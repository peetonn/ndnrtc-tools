#!/usr/bin/env python

import lxml
import requests
from lxml import html
import sys
from collections import OrderedDict
import re

if '__main__' == __name__:
	if len(sys.argv) > 1:
		webpage = sys.argv[1]
	else:
		print "usage "+__name__+" <webpage_url>"
		print "This script parses webpage at <webpage_url> and looks for the table of testbed hubs."
		print "It is supposed to be testbed status webpage: http://arl.wustl.edu/~jdd/ndnstatus/ndn_prefix/tbs_ndnx.html"
		exit(1)
	page=requests.get(webpage)
	tree=html.fromstring(page.text)
	labels=tree.xpath('//table/tr[1]/td/a/font/text()')
	urls=tree.xpath('//table/tr[1]/td/a/@href')
	urls2=tree.xpath('//table/tr[position()>1]/td/a/@href')
	prefixes=tree.xpath('//table/tr[position()>1]/td/a/font/text()')
	
	if len(urls) != len(labels) or len(urls2) != len(prefixes):
		print "something is wrong..."
		exit(1)

	nodeUrls = OrderedDict()
	nodeLabels = OrderedDict()
	nodePrefixes = OrderedDict()

	i = 0
	for url in urls2:
		m = re.match(r"http://(?P<name>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})|(([0-9A-z-]+)\.?)+)(:80)?",urls[i])
		if m :
			nodeUrl = m.group('name')
			nodePrefix = prefixes[i].split('ndn:')[1]
			nodePrefixes[nodeUrl] = nodePrefix
		i += 1

	i = 0
	for label in labels:
		m = re.match(r"http://(?P<name>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})|(([0-9A-z-]+)\.?)+)(:80)?",urls[i])
		if m:
			nodeUrl = m.group('name')
			nodeUrls[label] = nodeUrl
			nodeLabels[nodeUrl] = label
			print label + "\t" + nodeUrls[label] + "\t" + nodePrefixes[nodeUrl]
		i += 1

