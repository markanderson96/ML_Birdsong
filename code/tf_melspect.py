#!/bin/python

from __future__ import absolute_import, division, print_function
import tensorflow as tf
import sys
import numpy as np
import matplotlib.pyplot as plt
import argparse
from scipy import signal

def opts_parser():
    parser = argparse.ArgumentParser()
    
    parser.add_argument('-i', '--input', type=str, required=True)
    parser.add_argument('-o', '--output', type=str, required=True)
    parser.add_argument('-f', '--frame_rate', type=float, default=100)
    parser.add_argument('-O', '--overlap', type=int, default=50)
    parser.add_argument('-b', '--bands', type=int, default=80)
    parser.add_argument('-m', '--min-freq', type=float, default=100)
    parser.add_argument('-M', '--max-freq', type=float, default=16000)
    parser.add_argument('-t', '--type', type=str, default='mel')
    parser.add_argument('-d', '--downsample', type=int)
    parser.add_argument('-p', '--preemphasis', action="store_true")

    return parser

def main():
    # Pasrse options
    parser = opts_parser()
    args = parser.parse_args()
    
    # Extract options
    audio_path = args.input
    output_file = args.output
    frame_rate = args.frame_rate
    overlap = args.overlap
    mel_bands = args.bands
    min_freq = args.min_freq
    max_freq = args.max_freq
    spect_type = args.type
    downsample = args.downsample
    preemphasis = args.preemphasis
   
    # Executes eagerly by default
    tf.executing_eagerly()
    print("Num GPUs Available: ", len(tf.config.experimental.list_physical_devices('GPU'))) # TODO Make use of GPU more

    audio_file = tf.io.read_file(audio_path) # read audio file
    waveform, sample_rate = tf.audio.decode_wav(audio_file) # decode wav

    waveform = np.array(waveform) # reshape audio to remove channel dimension
    waveform = waveform.reshape(waveform.shape[0])

    sample_rate = tf.cast(sample_rate, tf.float32) # cast sr as float (needed for mel weighting)
    
    if (downsample):
        waveform = signal.decimate(waveform, downsample)
        sample_rate = sample_rate//downsample
        print(sample_rate)

    frame_length = int((sample_rate/frame_rate) * (1 + overlap/100))

    if (spect_type == 'linear'):
        Wl = min_freq / (sample_rate//2)
        Wh = max_freq / (sample_rate//2)
        b, a = signal.cheby2(4, 40, [Wl, Wh], 'bandpass')
        waveform = signal.lfilter(b, a, waveform)
    
    if (preemphasis):
        waveform = signal.lfilter([1, -0.95], 1, waveform)

    hop = int(sample_rate/frame_rate) # Calculate frame step

    stfts = tf.signal.stft(waveform, frame_length, hop, window_fn=tf.signal.hann_window) # take stft and absolute
    spectrograms = tf.abs(stfts)
    
    if (spect_type == 'mel'):
        print('Making Mel Spectrogram')
        num_fft_bins = stfts.shape[-1] # num fft bins
        mel_weights = tf.signal.linear_to_mel_weight_matrix(mel_bands, num_fft_bins, sample_rate, min_freq, max_freq) # create filterbank
        spect = tf.tensordot(spectrograms, mel_weights, 1) # apply to stft
        #mel_spectrogram.set_shape(spectrograms.shape[:-1].concatenate(mel_weights.shape[-1:]))
    else:
        print('Making Linear Spectrogram')
        spect = spectrograms

    mul = tf.multiply(spect, 64) # Change this to normalisation
    expanded = tf.expand_dims(mul, -1) # Needed to create image

    # Spectrogram is backwars and axes swapped, below code fixes this
    flipped = tf.image.flip_left_right(expanded)
    transposed = tf.image.transpose(flipped)

    # Cast to 8-bit unisgned
    out = tf.cast(transposed, tf.uint8)
    
    # Write out PNG of Spectrogram
    tf.io.write_file(output_file, tf.image.encode_png(out, compression=0))

if __name__=="__main__":
	main()
