import numpy as np
import time

import ctypes
from picosdk.ps4000 import ps4000 as ps


class picoscope4000:
    def __init__(self):
        self.chandle = ctypes.c_int16()
        self.channels = {'A':channel(self, chan='A'), 'B':channel(self, chan='B')}
        self.streaming = False
        self.overflow = False
        self.dt_nanos = None
    def close(self):
        '''Disconnect from the scope'''
        ps.ps4000CloseUnit(self.chandle)
        self.__init__()
    def connect(self):
        '''Connect to the scope'''
        # Open PicoScope 4000 Series device
        # Returns handle to chandle for use in future API functions
        assert 0 == ps.ps4000OpenUnit(ctypes.byref(self.chandle))
    def set_channel(self, chan:str, enable:bool, rng:float, coupling:str):
        '''Set channels on the picoscope.'''
        self.channels[chan].set(rng=rng, coupling=coupling, enable=enable)
    def stream_setup(self, duration:float, dt:float):
        '''Setup parameters for streaming. 
        duration: The time in seconds to stream
        dt: ESTIMATED the sampling interval, a float in seconds. The picoscope SDK will round this down to the nearest 100 ns. 
        picoscope4000.get_dt() will give the real dt after this function has been called.
        NOTE: The picoscope 4262 only accepts multiples of 100 ns, and for 
        two-channel acquisition, it can do 100 ns for only about a second.
        Unclear why the documentation says that with the SDK it can do 6.7 MHz (150 ns) streaming.'''
        # Begin streaming mode:
        if self.streaming:
            raise ValueError('Already streaming!')
        self.streaming = True
        self.overflow = False
    
        self.totalSamples = int( np.round( duration/dt ) )

        sampleUnits = ps.PS4000_TIME_UNITS['PS4000_NS']
        self.sampleInterval = ctypes.c_int32(int(np.round(dt*1e9))) #must be more than 150 nanoseconds in two-channel mode...?
        # maybe even more than 200 ns? It works at 100 ns for about a second. Also, it seems this will round down to the nearest 100 ns.
    
        for _,ch in self.channels.items():
            ch.buffer_initialize()

        # We are not triggering:
        maxPreTriggerSamples = 0
        autoStopOn = 1
        # No downsampling:
        downsampleRatio = 1

        assert 0 == ps.ps4000RunStreaming(self.chandle,
            ctypes.byref(self.sampleInterval),
            sampleUnits,
            maxPreTriggerSamples,
            self.totalSamples,
            autoStopOn,
            downsampleRatio,
            min(self.totalSamples, channel.BUFFER_ALLOC))
        self.dt_nanos = self.sampleInterval.value # THIS LINE HAS TO COME AFTER ps4000RunStreaming(...).
    
        def _callback(handle, noOfSamples, buff_start_idx, overflow, triggerAt, triggered, autoStop, param):
            if autoStop:
                self.streaming = False
                self.stop()
            self.buffer_start = buff_start_idx
            self.buffer_end = buff_start_idx + noOfSamples
            self.overflow = (overflow != 0)
        # Convert the python function into a C function pointer.
        self.cFuncPtr = ps.StreamingReadyType( _callback )
        self.buffer_start = 0
        self.buffer_end = 0
    def stream_latest(self):
        '''Call this to put the latest streamed data into the buffers. Must be called after stream_setup has been called.'''
        if not self.streaming:
            raise ValueError('Not currently streaming!')
        if self.overflow:
            print(f'WARNING! Buffer overflowed or channel out of range!')
        ps.ps4000GetStreamingLatestValues(self.chandle, self.cFuncPtr, None)
    def get_latest_streamed_data(self) ->dict[str,np.ndarray]:
        '''returns a dict with numpy arrays corresponding to the latest data that has been streamed.'''
        idx = np.arange(self.buffer_start, self.buffer_end) % channel.BUFFER_ALLOC
        res = {k:ch.ring_buffer[idx] for k,ch in self.channels.items()}
        # NOTE to self: not putting this here made a non-obvious bug
        #  based on just how quickly data was taken out, wasted so much time
        self.buffer_start = self.buffer_end%channel.BUFFER_ALLOC
        return res
    def stop(self):
        # Stop the scope
        ps.ps4000Stop(self.chandle)
        self.streaming = False
    def get_dt(self)->float:
        return self.dt_nanos*1e-9


class channel:
    BUFFER_ALLOC = 16000000
    MAX_ADC = 2**15 - 1
    VOLT_RANGES = (00.01, 00.02, 00.05, 
                   00.10, 00.20, 00.50,
                   01.00, 02.00, 05.00, 
                   10.00, 20.00 )
    def __init__(self, scope:picoscope4000, chan:str):
        self.parent_scope = scope
        if chan not in ('A', 'B'):
            raise ValueError('Invalid channel. Should be "A" or "B".')
        else:
            self.chan = chan
        self.rng = None
        self.coupling = None
        self.enabled = None
        self.chan = chan
    def _chan(self):
        return ps.PS4000_CHANNEL[f'PS4000_CHANNEL_{self.chan}']
    def _rng(self):
        if   self.rng == 0.01:
            return ps.PS4000_RANGE['PS4000_10MV']
        elif self.rng == 0.02:
            return ps.PS4000_RANGE['PS4000_20MV']
        elif self.rng == 0.05:
            return ps.PS4000_RANGE['PS4000_50MV']
        elif self.rng == 0.1:
            return ps.PS4000_RANGE['PS4000_100MV']
        elif self.rng == 0.2:
            return ps.PS4000_RANGE['PS4000_200MV']
        elif self.rng == 0.5:
            return ps.PS4000_RANGE['PS4000_500MV']
        elif self.rng == 1:
            return ps.PS4000_RANGE['PS4000_1V']
        elif self.rng == 2:
            return ps.PS4000_RANGE['PS4000_2V']
        elif self.rng == 5:
            return ps.PS4000_RANGE['PS4000_5V']
        elif self.rng == 10:
            return ps.PS4000_RANGE['PS4000_10V']
        elif self.rng == 20:
            return ps.PS4000_RANGE['PS4000_20V']
        else:
            raise ValueError(f'Invalid voltage range {self.rng}')
    def _coupling(self):
        if self.coupling not in ('AC','DC'):
            raise ValueError(f'Coupling must either be AC or DC, not {self.coupling}')
        return ps.PICO_COUPLING[self.coupling]
    def _enabled(self):
        return int(self.enabled)
    def set(self, rng:float, coupling:str, enable:bool):
        # Available PS4000_RANGEs: {
            # 'PS4000_10MV': 0, 'PS4000_20MV': 1, 'PS4000_50MV': 2,
            # 'PS4000_100MV': 3, 'PS4000_200MV': 4, 'PS4000_500MV': 5, 
            # 'PS4000_1V': 6, 'PS4000_2V': 7, 'PS4000_5V': 8, 
            # 'PS4000_10V': 9, 'PS4000_20V': 10, 
        # Available but not sure why/what they do: 
            # 'PS4000_50V': 11, 'PS4000_100V': 12, 'PS4000_RESISTANCE_100R': 13, 'PS4000_MAX_RANGES': 13, 'PS4000_RESISTANCE_1K': 14, 'PS4000_RESISTANCE_10K': 15, 'PS4000_RESISTANCE_100K': 16, 'PS4000_RESISTANCE_1M': 17, 'PS4000_ACCELEROMETER_10MV': 18, 'PS4000_MAX_RESISTANCES': 18, 'PS4000_ACCELEROMETER_20MV': 19, 'PS4000_ACCELEROMETER_50MV': 20, 'PS4000_ACCELEROMETER_100MV': 21, 'PS4000_ACCELEROMETER_200MV': 22, 'PS4000_ACCELEROMETER_500MV': 23, 'PS4000_ACCELEROMETER_1V': 24, 'PS4000_ACCELEROMETER_2V': 25, 'PS4000_ACCELEROMETER_5V': 26, 'PS4000_ACCELEROMETER_10V': 27, 'PS4000_ACCELEROMETER_20V': 28, 'PS4000_ACCELEROMETER_50V': 29, 'PS4000_ACCELEROMETER_100V': 30, 'PS4000_TEMPERATURE_UPTO_40': 31, 'PS4000_MAX_ACCELEROMETER': 31, 'PS4000_TEMPERATURE_UPTO_70': 32, 'PS4000_TEMPERATURE_UPTO_100': 33, 'PS4000_TEMPERATURE_UPTO_130': 34, 'PS4000_RESISTANCE_5K': 35, 'PS4000_MAX_TEMPERATURES': 35, 'PS4000_RESISTANCE_25K': 36, 'PS4000_RESISTANCE_50K': 37, 'PS4000_MAX_EXTRA_RESISTANCES': 38}
        self.rng = rng
        self.coupling = coupling
        self.enabled = bool(enable)

        assert 0 == ps.ps4000SetChannel(self.parent_scope.chandle,
            self._chan(),
            self._enabled(),
            self._coupling(),
            self._rng())
    def buffer_initialize(self):
        '''Need two buffers here. 
            One is the ring buffer used by the picoscope, but it is capped at ~1e6 points.
            The other is for the arbitrary length of data acquired while streaming, which will be
            filled from the first buffer.'''
        self.ring_buffer = np.zeros(shape=channel.BUFFER_ALLOC, dtype=np.int16)
        # if channel.BUFFER_ALLOC < totalSamples:
        # else:
        #     self.ring_buffer = np.zeros(shape=totalSamples, dtype=np.int16)
        # Set data buffer location for data collection
        # handle = chandle
        # source = PS4000_CHANNEL_A  or B
        # pointer to buffer max = ctypes.byref(bufferAMax)
        # pointer to buffer min = ctypes.byref(bufferAMin)
        # buffer length = maxSamples
        # segment index = 0 ???
        # ratio mode = PS4000_RATIO_MODE_NONE = 0
        assert 0 == ps.ps4000SetDataBuffers(
            self.parent_scope.chandle,
            self._chan(),
            self.ring_buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)),
            None,
            channel.BUFFER_ALLOC)
                
        # We need a big buffer, not registered with the driver, to keep our complete capture in.
    def get_volt_range(self):
        return self.rng
    def get_volt_scale(self):
        return self.get_volt_range()/channel.MAX_ADC


if __name__ == '__main__':
    def timeit(callable):
        t0 = time.time()
        callable()
        print('That took', time.time()-t0)

    pico = picoscope4000()
    pico.connect(A_range=1, B_range=2)

    pico.stream_setup(3, (150, 'nanos'))
    timeit(pico.stream)

    pico.stream_setup(1, (150, 'nanos'))
    timeit(pico.stream)