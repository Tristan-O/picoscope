from picoscope4000 import picoscope4000
from Buffer import BinnedRingBuffer

import os, json, datetime
import numpy as np
import h5py
import eel


default = {} #in case the file doesn't exist
try:
    with open(f'default.json', 'r') as f:
        default = json.load(f)
        if not default['directory'].endswith('\\'):
            default['directory'] = default['directory'][:-1]
except Exception as e:
    print(f'Could not find default.json ({e})')
    if 'directory' not in default.keys():
        print('Making a new one for you...')
        if os.path.exists(os.path.expanduser('~\\Documents')):
            default['directory'] = os.path.expanduser('~\\Documents')
        elif os.path.exists(os.path.expanduser('~\\My Documents')):
            default['directory'] = os.path.expanduser('~\\My Documents')
        else:
            default['directory'] = os.path.expanduser('~')
    if not default['directory'].endswith('\\') and not default['directory'].endswith('/'):
        default['directory'] = default['directory']+'\\'
    with open(f'default.json', 'w') as f:
        json.dump(default, f)
        print('default.json has been created!')
eel.init('web') #name of the directory that has the html


MAX_N_BINS = 100000
pico = picoscope4000()
try:
    pico.connect()
except Exception as e:
    print('ERROR: Picoscope not connected!', e)
buffA = BinnedRingBuffer(size=2, dtype=np.int16)
buffB = BinnedRingBuffer(size=2, dtype=np.int16)
stream_times = []

def debug(*args):
    if False:
        print(*args)


@eel.expose
def py_pico_reconnect():
    debug('in py_pico_reconnect')

    pico.close()
    pico.connect()

@eel.expose
def py_pico_set_channel(chan:str, enable:bool, rng:float, coupling:str):
    debug('in py_pico_set_channels', chan, enable, rng, coupling)

    pico.set_channel(chan=chan, enable=enable, rng=rng, coupling=coupling)

@eel.expose
def py_pico_stream_setup(stream_duration:float, buffer_duration:float, dt:float):
    debug('in py_pico_stream_setup', stream_duration, buffer_duration, dt)

    buffsize = int(buffer_duration/dt)

    buffA.reset(size=buffsize)
    buffB.reset(size=buffsize)

    stream_times.append(datetime.datetime.now())
    pico.stream_setup( stream_duration, dt )

    return pico.get_dt() #pico will change dt

@eel.expose
def py_get_x_data(binsize:int):
    debug('in py_get_x_data', binsize)

    if len(buffA):
        time = np.linspace(0, pico.get_dt()*len(buffA),
                           min(MAX_N_BINS, buffA.data.size//binsize)).tolist()
        freq = np.fft.rfftfreq(len(time), time[1]-time[0]).tolist()
    elif len(buffB):
        time = np.linspace(0, pico.get_dt()*len(buffB),
                           min(MAX_N_BINS, buffB.data.size//binsize)).tolist()
        freq = np.fft.rfftfreq(len(time), time[1]-time[0]).tolist()
    else:
        time = []
        freq = []

    return { 'time':time, 'freq':freq }

@eel.expose
def py_pico_stream_to_buff():
    debug('in py_pico_stream_to_buff')

    pico.stream_latest()
    res = pico.get_latest_streamed_data()

    if pico.channels['A'].enabled and len(res['A']):
        buffA.extend(res['A'])
    if pico.channels['B'].enabled and len(res['B']):
        buffB.extend(res['B'])

    return pico.overflow

@eel.expose
def py_get_buff_data(binsize:int):
    debug('in py_get_buff_data', binsize)

    binsize = max(binsize, buffA.data.size//MAX_N_BINS)

    return { 'A': (buffA.get_data(binsize)*pico.channels['A'].get_volt_scale()).tolist() ,
             'B': (buffB.get_data(binsize)*pico.channels['B'].get_volt_scale()).tolist() }

@eel.expose
def py_pico_is_streaming():
    debug('in py_pico_is_streaming')

    return pico.streaming

@eel.expose
def py_get_psd(binsize:int):
    '''Get PSD data in V^2/Hz.'''
    debug('in py_get_fft', binsize)

    binsize = max(binsize, buffA.data.size//MAX_N_BINS)
    res = {}
    # Computing the PSD:
    #  numpy does not normalize the FFT by default. 
    try:
        scale = pico.channels['A'].get_volt_scale()*pico.get_dt()*binsize/(len(buffA)//binsize)
        res['A'] = (np.abs(np.fft.rfft(buffA.get_data(binsize))**2)*scale).tolist()
    except Exception as e:
        res['A'] = []
    
    try:
        scale = pico.channels['B'].get_volt_scale()*pico.get_dt()*binsize/(len(buffB)//binsize)
        res['B'] = np.abs(np.fft.rfft(buffB.get_data(binsize)*scale)).tolist()
    except Exception as e:
        res['B'] = []

    return res

@eel.expose
def py_get_psd_integral(fLo:float, fHi:float):
    '''Get integral of PSD over bandwidth defined by (fLo, fHi)
    '''

    if len(buffA):
        freq = np.fft.rfftfreq(len(buffA), pico.get_dt())
        scale = pico.channels['A'].get_volt_scale()*pico.get_dt()/(len(buffA))
        psd = (np.abs(np.fft.rfft(buffA.get_data(1))**2)*scale)
        resA = np.sum( psd[(fLo<freq)*(freq<fHi)] )*(freq[1]-freq[0])
    else:
        resA = None
    if len(buffB):
        freq = np.fft.rfftfreq(len(buffB), pico.get_dt())
        scale = pico.channels['B'].get_volt_scale()*pico.get_dt()/(len(buffB))
        psd = (np.abs(np.fft.rfft(buffB.get_data(1))**2)*scale)
        resB = np.sum( psd[(fLo<freq)*(freq<fHi)] )*(freq[1]-freq[0])
    else:
        resB = None

    return {'A':resA, 'B':resB}

@eel.expose
def py_pico_stop():
    debug('in py_pico_stop')

    pico.stop()

@eel.expose
def py_get_dir_structure():
    debug('in py_get_dir_structure')

    root_dir = default['directory']
    if not root_dir.endswith('\\'):
        root_dir = root_dir+'\\'
    dir_structure = []

    def exclude(dir:str)->bool:
        if dir.startswith('.'):
            return True
        elif dir == '__pycache__':
            return True
        return False

    for root, dirs, _ in os.walk(root_dir, topdown=True):
        #skip dirs like .git
        dirs[:] = [d for d in dirs if not exclude(d)]

        root = root_dir.split('\\')[-2] + '\\' + root.replace(root_dir, '')
        for dir in dirs:
            path = os.path.join(root, dir).replace('/', '\\') #just to make sure we're using \ not /
            dir_structure.append(path)

    return sorted( dir_structure )

@eel.expose
def py_save_buff(dir:str, file_suffix:str, binsize:int):
    debug('in py_save_buff', dir, file_suffix, binsize)

    #dir here is from the default starting dir
    try:
        path = ( default['directory'] + '\\' + dir + '\\' +
                 stream_times[-1].strftime(file_suffix) )
        if not os.path.exists(os.path.dirname(path)):
            path = ( default['directory'] + '\\'.join(dir.split('/')[1:]) + '\\' +
                     stream_times[-1].strftime(file_suffix) )

        if not path.endswith('.hdf5'):
            path = path + '.hdf5'
        path = path.replace('\\', '/').replace('//', '/').replace('//', '/').replace('//', '/')

        with h5py.File(path, "w") as f:
            root = stream_times[-1].strftime('%Y%m%d_%H%M%S')
            grp = f.create_group(root)

            grp.create_dataset('A_data', data = buffA.get_data(binsize) )
            grp.create_dataset('B_data', data = buffB.get_data(binsize) )

            grp.create_dataset('A_volt_scale', data = pico.channels['A'].get_volt_scale())
            grp.create_dataset('B_volt_scale', data = pico.channels['B'].get_volt_scale())

            grp.create_dataset('A_volt_offset', data = 0)
            grp.create_dataset('B_volt_offset', data = 0)

            grp.create_dataset('t_per_pt_sec_before_bin', data = pico.get_dt()) # done this way because the picoscope does int casting
            grp.create_dataset('binsize', data = binsize)
            grp.create_dataset('t_per_pt_sec', data = pico.get_dt()*binsize) # done this way because the picoscope does int casting

            grp.create_dataset('acquire_timestamp', data = stream_times[-1].timestamp())
            grp.create_dataset('acquire_datetime',  data = stream_times[-1].strftime('%Y/%m/%d %H:%M:%S'))

            grp.create_dataset('data_notes', data='To scale data from ADCs to volts, multiply by volt_scale, NOT volt_range. If the data is binned, the binsize indicates how large the bins were. t_per_pt_sec is always the effective sampling rate after binning, in seconds. Timestamp is the time that the acquisition began. The picoscope does not seem reliable at the max sampling rate of 10 MHz when acquiring two channels - the sampling rate seems to fall to 5 MHz after about a second, but the picoscope will not tell you this has happened. The picoscope does not allow arbitrary sampling rates; it will always truncate the time between points to the nearest multiple of 100 ns. This means that you cannot set it to 6.7 MHz (max two-channel acquisition speed from the datasheet) which is ~150 ns per point.')
            
            grp.create_dataset('A_volt_range', data = pico.channels['A'].get_volt_range())
            grp.create_dataset('B_volt_range', data = pico.channels['B'].get_volt_range())
            grp.create_dataset('A_enabled', data = pico.channels['A'].enabled)
            grp.create_dataset('B_enabled', data = pico.channels['B'].enabled)
            grp.create_dataset('A_coupling', data = pico.channels['A'].coupling)
            grp.create_dataset('B_coupling', data = pico.channels['B'].coupling)

        print(f'File saved to {path}')
        return True, f'File saved!', path
    except Exception as e:
        print('FILE NOT SAVED! ERROR: ', e)
        return False, f'ERROR: File NOT saved!', str(e)

@eel.expose
def py_from_file(path:str):
    raise NotImplementedError
    with h5py.File(path, 'r') as f:
        pass


# Start the Eel application
eel.start('main.html', cmdline_args=['--start-maximized'])
