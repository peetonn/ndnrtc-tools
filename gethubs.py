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
		print "usage "+__name__+" <webpage>"
		eixt()
	page=requests.get(webpage)
	tree=html.fromstring(page.text)
	labels=tree.xpath('//table/tr[1]/td/a/font/text()')
	urls=tree.xpath('//table/tr[1]/td/a/@href')
	
	if len(urls) != len(labels):
		print "something is wrong..."
		exit()
	nodes = OrderedDict()
	i = 0
	for label in labels:
		m = re.match(r"http://(?P<name>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})|(([0-9A-z-]+)\.?)+)(:80)?",urls[i])
		nodes[label] = m.group('name')
		print label + "\t" + nodes[label]
		i += 1

