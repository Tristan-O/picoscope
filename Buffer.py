# https://scimusing.wordpress.com/2013/10/25/ring-buffers-in-pythonnumpy/
import numpy as np

class StaticBuffer:
    def __init__(self, size, dtype=np.float64):
        self.dtype = dtype
        self.data = np.zeros(size, dtype=dtype)
        self.index = 0
        self.full = False
    def __len__(self):
        if self.full:
            return self.data.size
        else:
            return self.index
    def __getitem__(self, slc):
        return self.data[:self.index][slc]
    def reset(self, **kwargs):
        '''Reset any of the constructor arguments of this Buffer'''
        temp = dict(size=self.data.size, dtype=self.data.dtype)
        temp.update(**kwargs)
        del self.data
        self.__init__(**temp)
    def extend(self, x:np.ndarray):
        if x.size+self.index > self.data.size:
            raise IndexError('Buffer not large enough!')
        slc = slice(self.index, self.index+x.size)
        self.data[slc] = x
        self.index += x.size
        if self.index == self.data.size-1:
            self.full = True
    def tolist(self):
        return self[:].tolist()


class RingBuffer(StaticBuffer):
    "A 1D ring buffer using numpy arrays"
    def extend(self, x):
        "Extends ring buffer by array x"
        if len(x) == 0:
            raise ValueError("Can't extend a zero-length object!")
        elif len(x) > self.data.size:
            self.data[:] = x[-self.data.size:]
            self.index = 0
            self.full = True
        else:
            x_index = (self.index + np.arange(len(x))) % self.data.size
            self.data[x_index] = x

            if x_index[-1] < self.index and not self.full:
                self.full = True
            self.index = x_index[-1] + 1
    def get_data(self):
        idx = (self.index + np.arange(len(self))) % len(self)
        return self.data[:idx]
    def tolist(self):
        return self.get_data().tolist()


class BinnedRingBuffer(RingBuffer):
    '''Class for making a binned ring buffer. Holds all data, but it
       only rolls in multiples of the binsize and returns binned data.'''
    def get_data(self, binsize:int=1)->np.ndarray:
        '''Bin first, then roll. This ensures that the same samples go into a bin 
           regardless of where index is, until those samples are overwritten.'''
        
        idx = (self.index//binsize + np.arange(len(self)//binsize)) % (len(self)//binsize)
        if self.full:
            arr = self.data
        else:
            arr = self.data[:self.index]

        if binsize != 1:
            new_shape = (arr.size//binsize, binsize)
            # first datapoint is always going to be weird because its bin will 
            # include old and new data so throw away that point after binning
            return np.mean(arr[:np.prod(new_shape)].reshape(new_shape), axis=1)[idx][1:]
        return arr[idx]
    def tolist(self, binsize:int=1)->list:
        return self.get_data(binsize).tolist()


def ringbuff_numpy_test():
    ringlen = 100000
    ringbuff = RingBuffer(ringlen)
    for i in range(40):
        ringbuff.extend(np.ones(10000, dtype=np.float64)) # write
        ringbuff.get() #read