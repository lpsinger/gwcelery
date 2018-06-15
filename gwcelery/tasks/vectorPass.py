import numpy as np
from lalframe import frread
# from ..celery import app

__author__ = 'Geoffrey Mo (geoffrey.mo@ligo.org)'

# input parameters
source = '/archive/frames/O2/hoft/H1/H-H1_HOFT_C00-11800/H-H1_HOFT_C00-1180098560-4096.gwf'
channel = 'H1:DMT-DQ_VECTOR' #'H1:GDS-CALIB_STATE_VECTOR'
gpsstart = 1180098560 # gps time to start analysis, typically beginning of source time
duration = 1 # in seconds
goodBits = [0,1] # bits in bitmask which need to be 1 for good data
sampleSize = 3 # samples to veto at a time, if necessary
logicType = 'allBad' # allBad = need all bits to fail goodbits to veto sample 
		     # oneBad = just one bit fails goodbits vetoes entire sample

def readGWF(source, channel, gpsstart, duration):
	'''Read .gwf file and outputs as time series'''
	timeseries = frread.read_timeseries(source, channel, start=gpsstart, duration=duration)
	return timeseries

def goodBit(binary, goodbits):
	'''Determine whether or not the a binary passes the bitmask. True = pass'''
	goodBitList = []
	for bit in goodbits:
		assert max(goodbits) <= len(binary)-1, '''The size of the largest
			good bit required exceeds the size of the word.'''
		if bit < len(binary):
			goodBitList.append(binary[len(binary)-1-bit] == '1')
	return all(goodBitList)


def resultsLists(source, channel, gpsstart, duration):
	'''Create lists of gps times, integers, binaries, and good/bad for each single data point'''
	timeseries = readGWF(source, channel, gpsstart, duration)
	timeList = []
	intsList = []
	binsList = []
	goodList = []
	for i in range(len(timeseries.data.data)):
		timeList.append(float(timeseries.epoch)+i*timeseries.deltaT)
		intsList.append(timeseries.data.data[i])
		binsList.append(np.binary_repr(timeseries.data.data[i]))
		goodList.append(goodBit(np.binary_repr(timeseries.data.data[i]), goodBits))
	return timeList, intsList, binsList, goodList

def spliceIntoSamples(sampleSize, someList):
	'''Splices a list into sublists of size sampleSize'''
	outList = [someList[i:i+sampleSize] for i in xrange(0, len(someList), sampleSize)]
	return outList

def samplePass(bitList, logicType):
	'''Given a list of lists of True/False values, representing whether or not
	the sample passes the good bit bitmask, and a logic type,
	returns a list of True/False values regarding whether or not the sample
	passes.
	The logic type 'oneBad' fails the entire sample if any one bit is False.
	The logic type 'allBad' fails the sample only if all bits are False.'''
	samplePass = []
	assert logicType == 'oneBad' or logicType == 'allBad', '''Please set logicType to 'oneBad'
	or 'allBad'.'''
	if logicType == 'oneBad':
		for sample in bitList:
			samplePass.append(all(sample))
		return samplePass
	if logicType == 'allBad':
		for sample in bitList:
			samplePass.append(any(sample))
		return samplePass

def checkVector(source, channel, gpsstart, duration, goodBits, sampleSize=1, logicType='oneBad'):
	'''This is the function which checks the vector.'''
	timeList, intsList, binsList, goodList = resultsLists(source, channel, gpsstart, duration)
	goodListInSamples = spliceIntoSamples(sampleSize, goodList)
	passFailForEachSample = samplePass(goodListInSamples, logicType)
	return passFailForEachSample 
	
