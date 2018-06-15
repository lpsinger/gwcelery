# This requires Python 3
import numpy as np
from lalframe import frread
# from ..celery import app

__author__ = 'Geoffrey Mo (geoffrey.mo@ligo.org)'

# input parameters
# ----------------------------------------------------------------------------
source = """/archive/frames/O2/hoft/H1/H-H1_HOFT_C00-11800
            /H-H1_HOFT_C00-1180098560-4096.gwf"""
# used as a test frame
channel = 'H1:DMT-DQ_VECTOR'
# could also use 'H1:GDS-CALIB_STATE_VECTOR'
gpsstart = 1180098560
# gps time to start analysis, typically beginning of source time
duration = 1
check_good_bits = [0, 1]
# bits in bitmask which need to be 1 for good data
sample_size = 3
# samples to veto at a time, if necessary
logic_type = 'allBad'
# allBad = need all bits to fail goodbits to veto
# oneBad = one bit fails goodbits vetoes entire sample


def read_gwf(source, channel, gpsstart, duration):
    """Read .gwf file and outputs as time series"""
    timeseries = frread.read_timeseries(
                    source, channel,
                    start=gpsstart, duration=duration)
    return timeseries


def check_good_bit(binary, goodbits):
    """Determine whether or not the a binary passes the bitmask. True = pass"""
    good_bit_list = []
    for bit in goodbits:
        assert max(goodbits) <= len(binary)-1, """The size of the largest
            good bit required exceeds the size of the word."""
        if bit < len(binary):
            good_bit_list.append(binary[len(binary)-1-bit] == '1')
    return all(good_bit_list)


def make_results_lists(source, channel, gpsstart, duration):
    """Create lists of gps times, integers, binaries, and good/bad
    for each single data point
    """
    timeseries = read_gwf(source, channel, gpsstart, duration)
    time_list = []
    ints_list = []
    bins_list = []
    good_list = []
    for i in range(len(timeseries.data.data)):
        time_list.append(float(timeseries.epoch)+i*timeseries.deltaT)
        ints_list.append(timeseries.data.data[i])
        bins_list.append(np.binary_repr(timeseries.data.data[i]))
        good_list.append(check_good_bit(
                np.binary_repr(timeseries.data.data[i]),
                check_good_bits))
    return time_list, ints_list, bins_list, good_list


def splice_into_samples(sample_size, some_list):
    """Splices a list into sublists of size sample_size"""
    spliced_list = [
               some_list[i:i+sample_size]
               for i in range(0, len(some_list), sample_size)]
    return spliced_list


def does_sample_pass(bit_list, logic_type):
    """Given a list of lists of True/False values, representing whether or not
    the sample passes the good bit bitmask, and a logic type,
    returns a list of True/False values regarding whether or not the sample
    passes.
    The logic type 'oneBad' fails the entire sample if any one bit is False.
    The logic type 'allBad' fails the sample only if all bits are False.
    """
    does_sample_pass_list = []
    assert logic_type == 'oneBad' or logic_type == 'allBad', """Please set
    logic_type to 'oneBad' or 'allBad'."""
    if logic_type == 'oneBad':
        for sample in bit_list:
            does_sample_pass_list.append(all(sample))
        return does_sample_pass_list
    if logic_type == 'allBad':
        for sample in bit_list:
            does_sample_pass_list.append(any(sample))
        return does_sample_pass_list


def check_vector(source, channel, gpsstart, duration, check_good_bits,
                 sample_size=1, logic_type='oneBad'):
    """This is the function which checks the vector."""
    time_list, ints_list, bins_list, good_list = make_results_lists(
                    source,
                    channel, gpsstart, duration)
    spliced_good_list = splice_into_samples(sample_size, good_list)
    pass_fail_for_each_sample = does_sample_pass(spliced_good_list, logic_type)
    return pass_fail_for_each_sample
