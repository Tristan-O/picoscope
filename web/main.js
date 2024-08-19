async function sleep(millis) {
    // sleep in millis
    await new Promise(r => setTimeout(r, millis));
}
function get_float(id) {
    return parseFloat(document.getElementById(id).value)
}
function get_int(id) {
    return parseInt(document.getElementById(id).value)
}
function startProgressBar(duration) {
    let progressBar = document.getElementById('progressBar');
    progressBar.textContent = ''
    progressBar.classList.remove('progress-bar-danger');
    
    var percentage = 0;
    var updateTime = 10;
    var intervalDuration = (duration * 1000); // Calculate interval duration for 100 updates
    var interval = setInterval(function() {
        percentage += parseInt(updateTime/intervalDuration*100);
        if (percentage > 100) {
            clearInterval(interval);
        } else {
            progressBar.style.width = percentage + '%';
        }
    }, updateTime);
    return interval
}
function disable(toggle) {
    const disable_me = document.querySelectorAll('.disable-me');
    disable_me.forEach(item => {
        item.disabled = toggle;
    });
    // document.getElementById('live-btn').disabled = false;
    // document.getElementById('single-btn').disabled = false;
}
async function select_dir() {
    if (dialog_window && !dialog_window.closed) {
        dialog_window.focus();
    } else {
        var url = "file_dialog.html"; // Replace with the path to your HTML file
        var windowName = "Select output directory";
        var windowFeatures = "width=600,height=600,toolbar=no,menubar=no,scrollbars=yes,resizable=yes,location=no,status=no,maximized=no";
        dialog_window = window.open(url, windowName, windowFeatures);
    }
}

async function pico_stop() {
    document.getElementById('live-tab').classList.remove('pulsing');
    document.getElementById('single-tab').classList.remove('pulsing');
    await eel.py_pico_stop()();
    stop_flag = false;
}
async function pico_reconnect() {
    disable(true);
    try {
        await eel.py_pico_reconnect()();
    } catch {
    }
    disable(false);
}
async function pico_set_channels() {
    let aenabled = document.getElementById('A-enable').checked;
    let arange = parseFloat(document.getElementById('A-range').value);
    let acoupling = document.getElementById('A-coupling').value;
    await eel.py_pico_set_channel('A', aenabled, arange, acoupling)();
    
    let benabled = document.getElementById('B-enable').checked;
    let brange = parseFloat(document.getElementById('B-range').value);
    let bcoupling = document.getElementById('B-coupling').value;
    await eel.py_pico_set_channel('B', benabled, brange, bcoupling)();
}

async function save_buff(binsize) {
    disable(true);
    try {
        if (!binsize) {
            binsize = get_int('binsize');
            if (!binsize || binsize<1) { //if still couldn't get a binsize
                binsize = 1;
            }
        }
        //this dir needs to be tacked on to the default starting dir
        let dir = document.getElementById('selected-directory').innerText
        let suffix = document.getElementById('file-suffix').value

        let msg = await eel.py_save_buff(dir, suffix, binsize)();
        
        console.log(msg)
        document.getElementById('toast-title').innerHTML = msg[1]
        document.getElementById('toast-body').innerHTML = msg[2]
        if (msg[0]) { 
            // returns false if saving failed
            document.getElementById('myToast').classList.add('toast-success')
            document.getElementById('myToast').classList.remove('toast-failure')
        } else {
            console.log('ERROR! Could not save: ', msg)
            document.getElementById('myToast').classList.remove('toast-success')
            document.getElementById('myToast').classList.add('toast-failure')
        }
    } catch {
    }
    disable(false);
    $('#myToast').toast('show')
}

async function plot() {
    let binsize = get_int('binsize');
    if (!binsize) {
        binsize = 1;
    }
    let x_data = await eel.py_get_x_data(binsize)();
    let time_data = await eel.py_get_buff_data(binsize)();
    let freq_data = await eel.py_get_psd(binsize)();

    if (document.getElementById('A-enable').checked) {
        Plotly.update("plotAtime", {x:[x_data.time], y:[time_data.A]}, {}, [0]);
        Plotly.update("plotAfreq", {x:[x_data.freq], y:[freq_data.A]}, {}, [0]);
    }
    if (document.getElementById('B-enable').checked) {
        Plotly.update("plotBtime", {x:[x_data.time], y:[time_data.B]}, {}, [0]);
        Plotly.update("plotBfreq", {x:[x_data.freq], y:[freq_data.B]}, {}, [0]);
    }
}
async function live() {
    disable(true);
    document.getElementById('live-btn').classList.add('btn-primary')
    document.getElementById('live-btn').classList.remove('btn-danger')
    try{
        if (!(document.getElementById('A-enable').checked || document.getElementById('B-enable').checked) ) {
            // nothing is enabled. Don't do anything.
            console.log('Warning: Neither channel is enabled. Doing nothing.')
            return;
        }

        running_flag = true;
        stop_flag = false;
        
        await pico_set_channels();
        
        let buffer_duration = get_float('live-window'); // window size
        let stream_duration = 60*60*24; // run for 1 day
        let dt = 1/get_float('live-fs'); // 1 ms per point
        
        dt = await eel.py_pico_stream_setup(stream_duration, buffer_duration, dt)(); // pico will update dt
        
        document.getElementById('live-fs').value = 1/dt
        document.getElementById('live-tab').classList.add('pulsing');
        
        let num_warn = 0;
        let last_warn = 0;
        while (running_flag) {
            let overflow = await eel.py_pico_stream_to_buff()();
            if (overflow) {
                document.getElementById('live-btn').classList.remove('btn-primary')
                document.getElementById('live-btn').classList.add('btn-danger')
                num_warn += 1;
                console.log('WARNING! Overflow or voltage out of range! x'+num_warn);
                last_warn = Date.now();
            } else if (Date.now() - last_warn > buffer_duration*1000) {
                // reset overflow warning if the offending overflow is off the screen
                document.getElementById('live-btn').classList.add('btn-primary')
                document.getElementById('live-btn').classList.remove('btn-danger')
            }
            
            await plot();
            
            if (! await eel.py_pico_is_streaming()()) {
                // restart stream
                console.log('Restarting live streaming')
                await eel.py_pico_stream_setup(stream_duration, buffer_duration, dt)();
            }
            
            if (stop_flag) {
                await pico_stop();
                break;
            }
        }
        running_flag = false;
    } catch (error) {
        console.log(error);
        await pico_reconnect();
    }
    disable(false);
}
async function single() {
    disable(true);
    document.getElementById('live-btn').classList.add('btn-primary')
    document.getElementById('live-btn').classList.remove('btn-danger')
    try {
        if (!(document.getElementById('A-enable').checked || document.getElementById('B-enable').checked) ) {
            // nothing is enabled. Don't do anything.
            console.log('Warning: Neither channel is enabled. Doing nothing.')
            return;
        }
        
        running_flag = true;
        stop_flag = false;
        
        await pico_set_channels();
        
        let buffer_duration = get_float('single-window'); // window size
        let stream_duration = buffer_duration; // make stream time the same as the buffer size
        let dt = 1/get_float('single-fs'); // time between points. Can't rely on this to be the real dt because pico does type casting, but it will be close.
        
        dt = await eel.py_pico_stream_setup(stream_duration, buffer_duration, dt)(); // pico will update dt
        
        document.getElementById('single-fs').value = 1/dt
        
        document.getElementById('single-tab').classList.add('pulsing');
        
        let interval = startProgressBar(buffer_duration);
        
        let progressBar = document.getElementById('progressBar');
        progressBar.classList.remove('progress-bar-danger')
        let num_warn = 0;
        
        while (running_flag) {
            let overflow = await eel.py_pico_stream_to_buff()();
            if (overflow) {
                num_warn += 1;
                console.log('WARNING! Overflow or voltage out of range! x' + num_warn);
                progressBar.classList.add('progress-bar-danger');
                progressBar.textContent = num_warn + ' overflow or out of range!';
            }
            
            if (stop_flag || ! await eel.py_pico_is_streaming()()) {
                try {
                    clearInterval( interval );
                    await pico_stop();
                } catch {
                }
                break;
            }
        }
        
        if ( document.getElementById('single-autosave').checked ) {
            await save_buff(1);
        }
        
        await plot();
        
        running_flag = false;
    } catch (error) {
        console.log(error);
        await pico_reconnect();
    }  
    disable(false);
}


// Initialize pico, plots
var running_flag = false;
var stop_flag = false;

var layout_time = {
    margin: {
        l: 50,
        r: 20,
        b: 50,
        t: 20,
        pad: 5
    }, title: false,
    xaxis: {title: {text: 'time (s)'}},
    yaxis: {title: {text: 'volt (V)'}} 
};
var layout_freq = {   
    margin: {
        l: 50,
        r: 20,
        b: 50,
        t: 20,
        pad: 5
    }, title: false, 
    xaxis: {title: {text: 'freq (Hz)'}},
    yaxis: {title: {text: 'PSD (V^2/Hz)'}} 
};

var data_A = {x:[], y:[],
    mode: 'lines'};
var data_B = {x:[], y:[],
    mode: 'lines', 
    marker:{color:'red'}};

Plotly.newPlot('plotAtime', [data_A], layout_time);
Plotly.newPlot('plotAfreq', [data_A], layout_freq);
Plotly.newPlot('plotBtime', [data_B], layout_time);
Plotly.newPlot('plotBfreq', [data_B], layout_freq);

document.getElementById('PSDscale').addEventListener('change', function() {
    var scale = this.value;
    Plotly.relayout('plotAfreq', {
        'yaxis.type': scale
    });
    Plotly.relayout('plotBfreq', {
        'yaxis.type': scale
    });
});

// For selecting an output directory. Initialize dialog_window, event listener
var dialog_window = null;
window.addEventListener('message', function(event) {
    // Check if the message is of the expected type
    if (event.data && event.data.type === 'selected-directory') {
        document.getElementById('selected-directory').textContent = event.data.fullPath;
    }
});

// Keeping input elements within bounds
document.getElementById('binsize').addEventListener('blur', function(event) {
    let binsize = get_int('binsize');
    if (!binsize || binsize < 1) {
        document.getElementById('binsize').value = 1;
    }
});
document.getElementById('live-fs').addEventListener('blur', function(event) {
    let fs = get_float('live-fs');
    let el = document.getElementById('live-fs');
    if (!fs || fs < parseFloat(el.min)) {
        el.value = el.min;
    }
});
document.getElementById('live-fs').addEventListener('change', function(event) {
    let fs = get_float('live-fs');
    let el = document.getElementById('live-dt');
    el.value = (1/fs).toFixed(7)
});
document.getElementById('single-fs').addEventListener('blur', function(event) {
    let fs = get_float('single-fs');
    let el = document.getElementById('single-fs');
    if (!fs || fs < parseFloat(el.min)) {
        el.value = 1000;
    } else if (fs > parseFloat(el.max)) {
        el.value = parseFloat(el.max);
    }
});
document.getElementById('single-fs').addEventListener('change', function(event) {
    let fs = get_float('single-fs');
    let el = document.getElementById('single-dt');
    el.value = (1/fs).toFixed(7)
});
document.getElementById('live-window').addEventListener('blur', function(event) {
    let window = get_float('live-window');
    let el = document.getElementById('live-window');
    if (!window || window < parseFloat(el.min)) {
        el.value = 1;
    } else if (window > parseFloat(el.max)) {
        el.value = parseFloat(el.max);
    }
});
document.getElementById('single-window').addEventListener('blur', function(event) {
    let window = get_float('single-window');
    let el = document.getElementById('single-window');
    if (!window || window < parseFloat(el.min)) {
        el.value = 1;
    } else if (window > parseFloat(el.max)) {
        el.value = parseFloat(el.max);
    }
});
