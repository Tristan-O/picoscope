# About

The EICN recently purchased a Picoscope 4262 2-channel oscilloscope with arbitrary waveform generation built-in. I want to be able to stream data from it and analyze it in real time with a GUI. I don't care about the waveform generation capability for now.

## Requisite installation

1. Install the Picoscope SDK <https://www.picotech.com/downloads/_lightbox/pico-software-development-kit-64bit>
2. Copy the picosdk-python-wrappers repository from github
3. Activate a python virtual environment, navigate to the copied repo, and run `pip install .`
4. Also relies on numpy, eel, and h5py for saving data.
5. Have to modify the directory in default.json to a real directory on your system.

## pyinstaller

As described in the Eel repo, in Anaconda prompt:

1. Navigate to this repo
2. `python -m eel eel_main.py web --noconfirm`, check app works
3. `python -m eel eel_main.py web --noconfirm --onefile`

## TODO

Due to the headache of getting local file structure in javascript, a "From File" feature currently does not exist, but the infrastructure to do such a thing exists in the current version.
