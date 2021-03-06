#!/usr/bin/env python
# ./ingest.py --username=freeculture --hub=remap --influx-adaptor --host=ec2-52-90-158-238.compute-1.amazonaws.com --iuser=ingest --ipassword=1ng3st --metrics=irate,bitrateIn,....

import requests
import sys
import re
import time
import getopt
import json
import os
import subprocess
import time
import errno
import stat
import json
import datetime
import threading
import thread
import signal
from copy import deepcopy
from influxdb import InfluxDBClient

resourcesToTrack = {'cpu_pct':'%cpu', 'mem_pct':'%mem', 'virtual_kb':'vsz', 'resident_kb':'rss'}

#******************************************************************************
def runCmd(cmd):
	resultStr = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).stdout.read()
	return resultStr

def getProcessPid(processName):
	getPidCmdTemplate = 'pgrep ^{0}$ | tr "\\n" "," | sed \'s/,$//\''

	cmd = getPidCmdTemplate.format(processName)
	pidStr = runCmd(cmd)
	if len(pidStr) > 0:
		try:
			pid = int(pidStr)
			return pid
		except Exception as e:
			print("troubles getting PID for "+processName+": "+pidStr)
	return None

def getProcessResources(processName):
	global resourcesToTrack
	getResourcesCmdTemplte = 'ps -h -p {0} -o {1}' # | awk \'NR>1\''

	pid = getProcessPid(processName)
	if pid:
		cmd = getResourcesCmdTemplte.format(pid, ','.join(resourcesToTrack.values()))
		resourcesStr = runCmd(cmd)
		resources = filter(lambda x: len(x) > 0, resourcesStr.split(' '))
		resDict = {}
		for i in range(0,len(resourcesToTrack)):
			label = resourcesToTrack.keys()[i]
			value = float(resources[i])
			resDict[label] = value
		return resDict
	return None

def getInterfaceBytes(iface):
	getReceivedBytesTemplate = "ifconfig "+str(iface)+" | grep 'RX bytes' | awk '{print $2}'"
	getSentBytesTemplate = "ifconfig "+str(iface)+" | grep 'TX bytes' | awk '{print $6}'"
	rxbytesStr = runCmd(getReceivedBytesTemplate)
	txbytesStr = runCmd(getSentBytesTemplate)
	if len(rxbytesStr.split(':')) == 2 and len(txbytesStr.split(':')) == 2:
		rxBytes = int(rxbytesStr.split(':')[1])
		txBytes = int(txbytesStr.split(':')[1])
		return (rxBytes, txBytes)
	return None

#******************************************************************************
# resource monitoring
def ingestProcessResources(adaptor, processName, tags, fields, resDict):
	metric = IngestAdaptor.metricGenericTemplate
	metric['tags'] = {'process':processName}
	for k in tags.keys():
		metric['tags'][k] = tags[k]
	for k in fields.keys():
		metric['fields'][k] = fields[k]

	metric['timestamp'] = time.time()*1000

	for m in resDict:
		md = deepcopy(metric)
		md['metric'] = m
		md['value'] = resDict[m]
		adaptor.metricFunc(md)

def ingestResources(adaptor, tags, fields, processResDict):
	for processName in processResDict:
		if processResDict[processName]:
			ingestProcessResources(adaptor, processName, tags, fields, processResDict[processName])

def ingestNetworkResources(adaptor, tags, fields, networkBytes, iface):
	metric = IngestAdaptor.metricGenericTemplate
	metric['tags'] = {'iface':iface}
	for k in tags.keys():
		metric['tags'][k] = tags[k]
	for k in fields.keys():
		metric['fields'][k] = fields[k]

	metric['timestamp'] = time.time()*1000

	md = deepcopy(metric)
	md['metric'] = "rxbytes"
	md['value'] = networkBytes[0]
	adaptor.metricFunc(md)

	md = deepcopy(metric)
	md['metric'] = "txbytes"
	md['value'] = networkBytes[1]
	adaptor.metricFunc(md)

def run(tags, fields, isTrackingNdncon, isTrackingNfd, ingestAdaptor, statCollector, networkInterface):
	ingestFrequency = 1.
	delta = 0.1
	appName = "ndnrtc-client"
	nfdName = "nfd"
	ndnconResources = None
	nfdResources = None
	networkBytes = None
	elapsed = 0
	while True:
		if elapsed >= 1/ingestFrequency:
			elapsed = 0
			if isTrackingNdncon:
				ndnconResources = getProcessResources(appName)
			if isTrackingNfd:
				nfdResources = getProcessResources(nfdName)
			if networkInterface:
				networkBytes = getInterfaceBytes(networkInterface)
				ingestNetworkResources(ingestAdaptor, tags, fields, networkBytes, networkInterface)
			ingestResources(ingestAdaptor, tags, fields, {appName:ndnconResources, nfdName:nfdResources})
		if statCollector:
			statCollector.run()
		time.sleep(delta)
		elapsed += delta

#******************************************************************************
# statistics gathering
class StatCollector(object):
	def __init__(self, keywords, ingestAdaptor, statFileFolder, tags, fields):
		self.keywords_ = keywords
		self.adaptor_ = ingestAdaptor
		self.tags_ = tags
		self.fields_ = fields
		self.path_ = statFileFolder
		self.fileWatcher_ = TextFileWatcher(self.path_, self.newLine, extensions = ['stat'])

	def newLine(self, file, line):
		# assume files are named "tag-producerName-streamName.stat"
		try:
			filename = os.path.basename(file.name).split('.')[0]
			clientData = filename.split('-')
			if len(clientData) < 3:
				raise Exception('File name has wrong format')
			self.extractMetric(line, clientData)
		except Exception as e:
			print('error reading new data from file '+file.name+': '+str(e))

	def run(self):
		self.fileWatcher_.loop(blocking=False)

	def extractMetric(self, line, clientData):
		metricsJson = self.extractJson(line)
		if metricsJson:
			jsonData  = {'stats': metricsJson, 'stream': {'user':clientData[1],'stream':clientData[2],'stat_group':clientData[0]}}
			if self.checkData(jsonData):
				self.sendMetric(jsonData)
			else:
				print('json does not have required fields')

	def extractJson(self, line):
		try:
			jsonData = json.loads(line)
			return jsonData
		except Exception as e:
			print("error parsing json %r: %r"%(e))
		return None

	def checkData(self, jsonData):
		# check for required fields
		if not self.checkJsonFields(jsonData, ['stats', 'stream']): return False
		if not self.checkJsonFields(jsonData['stream'], ['user','stream','stat_group']):
			return False
		if not self.checkJsonFields(jsonData['stats'], ['timestamp']): return False
		foundKw = 0
		for kw in self.keywords_:
			if kw in jsonData['stats']: foundKw += 1
		# if foundKw == 0: return False
		# elif foundKw < len(self.keywords_): print('not all keywords were found. continued.')
		return True

	def checkJsonFields(self, jsonData, fields):
		for field in fields:
			if not field in jsonData: return False
		return True

	def sendMetric(self, jsonData):
		metric = deepcopy(IngestAdaptor.metricGenericTemplate)
		metric['tags'] = {'process':'headless', 'producer':jsonData['stream']['user'],\
			'consumer':self.tags_['user'], 'stream': jsonData['stream']['stream'],
			'stat-group': jsonData['stream']['stat_group']}
		for k in self.tags_.keys():
			metric['tags'][k] = self.tags_[k]
		for k in self.fields_.keys():
			metric['fields'][k] = self.fields_[k]
		metric['timestamp'] = jsonData['stats']['timestamp']
		# we name metric from stat group name
		# its' value will be the first value in json
		# other values will be fields
		# for example, this metric captured from "buffering-client1-camera.stat" (stat group 'buffering'): 
		#		{"timestamp":1467760216321.00,"jitterPlay":139.00,"jitterEst":241.00,"jitterTar":150.00}
		# therefore, metric will be:
		# { 'metric': 'buffering'; 'value':139, 'fields':{"jitterPlay":139.00,"jitterEst":241.00,"jitterTar":150.00}; ...}
		metric['metric'] = jsonData['stream']['stat_group']
		for kw in self.keywords_:
			metricNamed = False
			if kw in jsonData['stats']:
				value = jsonData['stats'][kw]
				if not metricNamed:
					metric['value'] = value
				metric['fields'][kw] = value
		self.adaptor_.metricFunc(metric)

#******************************************************************************
# classes borrowed & adapted from https://github.com/peetonn/ndnrtc-tools
#******************************************************************************
class IngestAdaptor(object):
	metricGenericTemplate = { 'metric' : None, 'timestamp': None, 'value': None, 'fields': {}, 'tags': {}}
	startTimestamp = None
	baseTimestamp = None
	timeOffset = 0
	writeCtr = 0
	lastWrite = 0
	metrics = []
	batchSize = 10
	dryRun = False
	metricWriteCounter = {}

	def __init__(self, timeOffset = 0):
		self.timeOffset = timeOffset
		self.baseTimestamp = 0
		self.batch = []
		self.lock = threading.Lock()
		self.running = True
		self.workerThread = thread.start_new_thread(self.processMetrics, ())
		signal.signal(signal.SIGINT, self.signal_handler)

	def signal_handler(self, signal, frame):
		self.finalize()
		self.stop()
		exit(0)

	def stop(self):
		self.running = False

	def connect(self):
		pass

	def timeFunc(self, match):
		return 0

	def fromMilliseconds(self, timestamp):
		return 0

	def fromUnixTimestamp(self, unixTimestamp):
		return 0

	def uniquefyTimestamps(self, metrics):
		timestamps = {}
		for metric in metrics:
			k = metric['timestamp']
			if k in timestamps.keys():
				timestamps[k] += 1
				metric['timestamp'] += timestamps[k]
				k = metric['timestamp']
			timestamps[k] = 0

	def writeBatch(self, metrics):
		pass

	def copyBatch(self, newBatch):
		if self.lock.acquire(False):
			batchCopy = deepcopy(newBatch)
			self.batch.extend(batchCopy)
			self.lock.release()
			return True
		else:
			return False

	def processMetrics(self):
		while self.running:
			self.lock.acquire()
			batchLen = len(self.batch)
			batchCopy = deepcopy(self.batch)
			self.batch = []
			self.lock.release()
			if batchLen > 0:
				if not self.dryRun:
					sys.stdout.write("writing batch of " + str(batchLen) + " metrics...")
				a = time.time()
				self.writeBatch(batchCopy)
				if not self.dryRun:
					sys.stdout.write(str(time.time()-a)+' sec\n')
				self.writeCtr += batchLen
				if self.writeCtr-self.lastWrite >= 1000 and not self.dryRun:
					print "wrote "+str(self.writeCtr-self.lastWrite)+" measurements. "+str(self.writeCtr)+" total."
					self.lastWrite = self.writeCtr
			time.sleep(0.1)

	def metricFunc(self, json):
		if not self.running: return
		self.metrics.append(json)
		if len(self.metrics) >= self.batchSize:
			if self.copyBatch(self.metrics):
				self.metrics = []
			else:
				sys.stdout.write('.')
		if not json['metric'] in self.metricWriteCounter.keys():
			self.metricWriteCounter[json['metric']] = 0
		self.metricWriteCounter[json['metric']] += 1

	def finalize(self):
		if len(self.metrics) > 0:
			self.writeBatch(self.metrics)
			self.writeCtr += len(self.metrics)
			self.metrics = []
		print("wrote "+str(self.writeCtr)+" measurements total")
		for key in self.metricWriteCounter.keys():
			print(key+': '+str(self.metricWriteCounter[key]))

	@staticmethod
	def printMetric(json):
		sys.stdout.write(str(json['metric'])+" "+str(json['timestamp'])+" "+str(json['value']))
		for key in json['tags'].keys():
			sys.stdout.write(' '+str(key)+'='+str(json['tags'][key]))
		for key in json['fields'].keys():
			sys.stdout.write(' '+str(key)+'='+str(json['fields'][key]))
		sys.stdout.write('\n')

	@staticmethod
	def printMetrics(metrics):
		for m in metrics:
			IngestAdaptor.printMetric(m)

class InfluxAdaptor(IngestAdaptor):
	influxClient = None
	influxJsonTemplate = { "measurement": None, "time": None, "fields": { "value": None }, "tags": {} }
	batchSize = 1000
	metrics = []

	def __init__(self, user, password, dbname, timeOffset = 0, host = 'localhost', port = 8086):
		super(InfluxAdaptor, self).__init__(timeOffset)
		self.connect(host, port, user, password, dbname)
		self.baseTimestamp = 1234560000000 # millisec

	def connect(self, host, port, user, password, dbname):
		self.influxClient = InfluxDBClient(host, port, user, password, dbname)

	def timeFunc(self, match):
		timestamp = int(match.group('timestamp'))
		if not self.startTimestamp:
			self.startTimestamp = timestamp
		unixTimestamp = self.baseTimestamp + (timestamp - self.startTimestamp)
		return unixTimestamp*1000000 # nanosec

	def fromMilliseconds(self, timestamp):
		return int(timestamp*1000000)

	def fromUnixTimestamp(self, unixTimestamp):
		return int(unixTimestamp*1000000000) # nanosec

	def writeBatch(self, metrics):
		if self.dryRun:
			IngestAdaptor.printMetrics(metrics)
		else:
			self.uniquefyTimestamps(metrics)
			batch = []
			for m in metrics:
				batch.append(self.toInfluxJson(m))
			try:
				self.influxClient.write_points(batch)
			except Exception as e:
				print('got error while trying to send metric: '+str(m) + '\n'+str(e))
				raise e

	def toInfluxJson(self, genericJson):
		influxJson = deepcopy(self.influxJsonTemplate)
		influxJson['measurement'] = genericJson['metric']
		influxJson['time'] = self.fromMilliseconds(genericJson['timestamp'])
		influxJson['fields']['value'] = genericJson['value']
		for key in genericJson['fields'].keys():
			influxJson['fields'][key] = genericJson['fields'][key]
		for key in genericJson['tags'].keys():
			influxJson['tags'][key] = genericJson['tags'][key]
		return influxJson

## DEPRECATED
class TsdbAdaptor(IngestAdaptor):
	tsdbJsonTemplate = { "metric": None, "timestamp": None, "value": None, "tags": {} }

	def __init__(self, timeOffset = 0, tsdbUri = 'http://localhost:4242/api/put?details', batchSize = 20):
		super(TsdbAdaptor, self).__init__(timeOffset)
		self.tsdbUri = tsdbUri
		self.batchSize = batchSize
		self.baseTimestamp = 1234560000000

	def timeFunc(self, match):
		timestamp = int(match.group('timestamp'))
		if not self.startTimestamp:
			self.startTimestamp = timestamp
		unixTimestamp = self.baseTimestamp + (timestamp - self.startTimestamp) + self.timeOffset
		return unixTimestamp

	def fromMilliseconds(self, timestamp):
		return timestamp

	def fromUnixTimestamp(self, unixTimestamp):
		return int(unixTimestamp*1000) # milisec

	def writeBatch(self, metrics):
		if self.dryRun:
			IngestAdaptor.printMetrics(metrics)
		else:
			tsdbMetrics = []
			for m in metrics:
				tsdbMetrics.append(self.toTsdbJson(m))
			response = requests.post(url=self.tsdbUri, data=json.dumps(tsdbMetrics), headers={'content-type': 'application/json'})
			if response.status_code != 200:
				print('return code '+str(response.status_code)+\
					'. aborting. info: '+response.text)
				exit(1)

	def toTsdbJson(self, genericJson):
		tsdbJson = deepcopy(self.tsdbJsonTemplate)
		tsdbJson['metric'] = genericJson['metric']
		tsdbJson['value'] = genericJson['value']
		tsdbJson['timestamp'] = genericJson['timestamp']
		for key in genericJson['fields'].keys():
			tsdbJson['tags'][key] = genericJson['fields'][key]
		for key in genericJson['tags'].keys():
			tsdbJson['tags'][key] = genericJson['tags'][key]
		return tsdbJson

#******************************************************************************
# text file watcher
# original code borrowed and adapted from http://code.activestate.com/recipes/577968-log-watcher-tail-f-log/
class TextFileWatcher(object):
    """Looks for changes in all files of a directory.
    This is useful for watching log file changes in real-time.
    It also supports files rotation.

    Example:

    >>> def callback(filename, lines):
    ...     print(filename, lines)
    ...
    >>> lw = LogWatcher("/var/log/", callback)
    >>> lw.loop()
    """

    def __init__(self, folder, callback, extensions=["log"], tail_lines=0,
                       sizehint=1048576):
        """Arguments:

        (str) @folder:
            the folder to watch

        (callable) @callback:
            a function which is called every time one of the file being
            watched is updated;
            this is called with "filename" and "lines" arguments.

        (list) @extensions:
            only watch files with these extensions

        (int) @tail_lines:
            read last N lines from files being watched before starting

        (int) @sizehint: passed to file.readlines(), represents an
            approximation of the maximum number of bytes to read from
            a file on every ieration (as opposed to load the entire
            file in memory until EOF is reached). Defaults to 1MB.
        """
        self.folder = os.path.realpath(folder)
        self.extensions = extensions
        self._files_map = {}
        self._callback = callback
        self._sizehint = sizehint
        self._readBuffer = ""
        self._verbose = False
        assert os.path.isdir(self.folder), self.folder
        assert callable(callback), repr(callback)
        self.update_files()
        for id, file in self._files_map.items():
            file.seek(os.path.getsize(file.name))  # EOF
            if tail_lines:
                try:
                    lines = self.tail(file.name, tail_lines)
                except IOError as err:
                    if err.errno != errno.ENOENT:
                        raise
                else:
                    if lines:
                        self._callback(file.name, lines)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        self.close()

    def loop(self, interval=0.1, blocking=True):
        """Start a busy loop checking for file changes every *interval*
        seconds. If *blocking* is False make one loop then return.
        """
        # May be overridden in order to use pyinotify lib and block
        # until the directory being watched is updated.
        # Note that directly calling readlines() as we do is faster
        # than first checking file's last modification times.
        while True:
            self.update_files()
            for fid, f in list(self._files_map.items()):
                self.readlines(f)
            if not blocking:
            	return
            time.sleep(interval)

    def log(self, line):
        """Log when a file is un/watched"""
        if self._verbose:
        	print(line)

    def listdir(self):
        """List directory and filter files by extension.
        You may want to override this to add extra logic or globbing
        support.
        """
        ls = os.listdir(self.folder)
        if self.extensions:
            return [x for x in ls if os.path.splitext(x)[1][1:] \
                                           in self.extensions]
        else:
            return ls

    @classmethod
    def open(cls, file):
        """Wrapper around open().
        By default files are opened in binary mode and readlines()
        will return bytes on both Python 2 and 3.
        This means callback() will deal with a list of bytes.
        Can be overridden in order to deal with unicode strings
        instead, like this:

          import codecs, locale
          return codecs.open(file, 'r', encoding=locale.getpreferredencoding(),
                             errors='ignore')
        """
        return open(file, 'r')

    @classmethod
    def tail(cls, fname, window):
        """Read last N lines from file fname."""
        if window <= 0:
            raise ValueError('invalid window value %r' % window)
        with cls.open(fname) as f:
            BUFSIZ = 1024
            # True if open() was overridden and file was opened in text
            # mode. In that case readlines() will return unicode strings
            # instead of bytes.
            encoded = getattr(f, 'encoding', False)
            CR = '\n' if encoded else b'\n'
            data = '' if encoded else b''
            f.seek(0, os.SEEK_END)
            fsize = f.tell()
            block = -1
            exit = False
            while not exit:
                step = (block * BUFSIZ)
                if abs(step) >= fsize:
                    f.seek(0)
                    newdata = f.read(BUFSIZ - (abs(step) - fsize))
                    exit = True
                else:
                    f.seek(step, os.SEEK_END)
                    newdata = f.read(BUFSIZ)
                data = newdata + data
                if data.count(CR) >= window:
                    break
                else:
                    block -= 1
            return data.splitlines()[-window:]

    def update_files(self):
        ls = []
        for name in self.listdir():
            absname = os.path.realpath(os.path.join(self.folder, name))
            try:
                st = os.stat(absname)
            except EnvironmentError as err:
                if err.errno != errno.ENOENT:
                    raise
            else:
                if not stat.S_ISREG(st.st_mode):
                    continue
                fid = self.get_file_id(st)
                ls.append((fid, absname))

        # check existent files
        for fid, file in list(self._files_map.items()):
            try:
                st = os.stat(file.name)
            except EnvironmentError as err:
                if err.errno == errno.ENOENT:
                    self.unwatch(file, fid)
                else:
                    raise
            else:
                if fid != self.get_file_id(st):
                    # same name but different file (rotation); reload it.
                    self.unwatch(file, fid)
                    self.watch(file.name)

        # add new ones
        for fid, fname in ls:
            if fid not in self._files_map:
                self.watch(fname)


        # check file lenghts
        for fid, file in list(self._files_map.items()):
            try:
                st = os.stat(file.name)
            except EnvironmentError as err:
                if err.errno == errno.ENOENT:
                    self.unwatch(file, fid)
                else:
                    raise
            else:
                if st.st_size < file.tell():
                    file.seek(st.st_size)
    def readlines(self, f):
        """Read file lines since last access until EOF is reached and
        invoke callback.
        """
        while True:
            bytes = f.readline(self._sizehint)
            if not bytes:
                break
            self.processBytes(f, bytes)
    
    def processBytes(self, f, bytes):
        self._readBuffer += bytes
        self.processBuffer(f)

    def processBuffer(self, file):
        alignedBuffer = True if self._readBuffer[-1] in ('\n','\r') else False
        lines = self._readBuffer.splitlines()
        if len(lines) == 1 and not alignedBuffer:
            pass
        wholeLines = lines[0:-1] if not alignedBuffer else lines
        for line in wholeLines:
            self._callback(file, line)
        if not alignedBuffer:
            self._readBuffer = lines[-1]
        else:
            self._readBuffer = ""

    def watch(self, fname):
        try:
            file = self.open(fname)
            fid = self.get_file_id(os.stat(fname))
        except EnvironmentError as err:
            if err.errno != errno.ENOENT:
                raise
        else:
            self.log("watching file %s" % fname)
            self._files_map[fid] = file

    def unwatch(self, file, fid):
        # File no longer exists. If it has been renamed try to read it
        # for the last time in case we're dealing with a rotating log
        # file.
        self.log("un-watching logfile %s" % file.name)
        del self._files_map[fid]
        with file:
            lines = self.readlines(file)
            if lines:
                self._callback(file.name, lines)

    @staticmethod
    def get_file_id(st):
        if os.name == 'posix':
            return "%xg%x" % (st.st_dev, st.st_ino)
        else:
            return "%f" % st.st_ctime

    def close(self):
        for id, file in self._files_map.items():
            file.close()
        self._files_map.clear()

#******************************************************************************
def usage():
	print "usage: "+sys.argv[0]+" --username=<user name> --hub=<home hub label> [--no-ndncon, --no-nfd]"
	print ""
	print "the tool allows to track CPU and memory resources consumed by ndncon and/or NFD and ingest "
	print "this data into remote data base for real-time and historical analysis"
	print ""
	print "\texample:"
	print "\t\t"+sys.argv[0]+" --username=peter --hub=remap"
	print "\toptions:"
	print "\t\t--no-nfd:\ttrack ndncon resources only"
	print "\t\t--no-ndncon:\ttrack NFD resources only"
	print "\texamples:"
	print "\t\ttrack CPU and memory consumption from ndncon only:"
	print "\t\t\t"+sys.argv[0]+" --username=peter --hub=remap --no-nfd"
	print "\t\ttrack CPU and memory consumption from NFD only:"
	print "\t\t\t"+sys.argv[0]+" --username=peter --hub=remap --no-ndncon"

def main():
	global resourcesToTrack

	try:
		opts, args = getopt.getopt(sys.argv[1:], "", ["username=", "hub=", \
			"no-ndncon", "no-nfd", "dry-run", "iuser=", "ipassword=", "idb=", \
			"influx-adaptor", "port=", "host=", "metrics=", "stat-folder=", "tags=", "iface=", "fields="])
	except getopt.GetoptError as err:
		print str(err)
		usage()
		exit(2)

	# ingestion parameters
	port = None
	host = 'localhost'
	tsdbPort = 4242
	influxPort = 8086
	useTsdbAdaptor = True
	dryRun = False
	influx_username = None
	influx_password = None
	influx_dataBaseName = None
	influx_resDB = "db_resources"
	influx_ndnrtcDB = "db_ndnrtc"

	username = None
	hubLabel = None
	trackNdncon = True
	trackNfd = True
	keywords = []
	statFolder = "/tmp"
	userTags = {}
	userFields = {}
	iface = None
	for o, a in opts:
		if o in ("--username"):
			userTags['user'] = a
			username = a
		elif o in ("--hub"):
			userTags['hubLabel'] = hubLabel
			hubLabel = a
		elif o in ("--no-ndncon"):
			trackNdncon = False
		elif o in ("--no-nfd"):
			trackNfd = False
		elif o in ("--dry-run"):
			dryRun = True
		elif o in ("--port"):
			port = int(a)
		elif o in ("--host"):
			host = a
		elif o in ("--influx-adaptor"):
			useTsdbAdaptor = False
		elif o in ("--iuser"):
			influx_username = a
		elif o in ("--ipassword"):
			influx_password = a
		elif o in ("--idb"):
			influx_dataBaseName = a
		elif o in ("--metrics"):
			keywords = a.split(',')
		elif o in ("--stat-folder"):
			statFolder = a
		elif o in ("--tags"):
			tagPairs = a.split(",")
			for pair in tagPairs:
				kv = pair.split("=")
				if len(kv) == 2:
					key = kv[0]
					value = kv[1]
					userTags[key] = value
		elif o in ("--fields"):
			fieldPairs = a.split(",")
			for pair in fieldPairs:
				kv = pair.split("=")
				if len(kv) == 2:
					key = kv[0]
					value = kv[1]
					userFields[key] = value
		elif o in ("--iface"):
			iface = a
		else:
			assert False, "unhandled option "+o
	if not username:
		usage()
		exit(2)

	if not useTsdbAdaptor and not (influx_username and influx_password):
		print influx_username, influx_password
		print "asked for influx adaptor, but didn't provide username or password. aborting"
		exit(2)

	if useTsdbAdaptor:
		if port: tsdbPort = port
		ingestAdaptor = TsdbAdaptor(timeOffset=0, tsdbUri='http://{0}:{1}/api/put?details'.format(host, tsdbPort))
	else:
		if port: influxPort = port
		ingestAdaptor = InfluxAdaptor(user=influx_username, password=influx_password, dbname=influx_resDB, timeOffset=0, host=host, port=influxPort)

	ingestAdaptor.batchSize = len(resourcesToTrack)+len(keywords)
	ingestAdaptor.dryRun = dryRun

	statCollector = None
	if len(keywords) > 0:
		print "tracking metrics: "+str(keywords)
		statCollector = StatCollector(keywords, ingestAdaptor, statFolder, userTags, userFields)

	if trackNdncon or trackNfd or statCollector:
		run(userTags, userFields, trackNdncon, trackNfd, ingestAdaptor, statCollector, iface)

if __name__ == '__main__':
	main()
