"""
GUSTO Pipeline utility functions

V. Tolls, SAO

created: 9/19/2024
"""

import numpy as np
from astropy import units as u
import astropy.constants as const
from astropy.coordinates import SkyCoord
from astropy.wcs import WCS, WCSSUB_LONGITUDE, WCSSUB_LATITUDE, WCSSUB_SPECTRAL
from astropy.wcs import validate as WCS_validate
from astropy.io import ascii, fits
from astropy.utils.exceptions import AstropyWarning
from scipy.interpolate import krogh_interpolate, barycentric_interpolate
from pprint import pprint
import parsl
from parsl.app.app import python_app, bash_app
from parsl.configs.local_threads import config
from parsl.providers import LocalProvider
from parsl.channels import LocalChannel
from parsl.config import Config
from parsl.executors import HighThroughputExecutor
import sys
import os
import re
import inspect
import datetime
import warnings
import pkg_resources
from astropy.io import fits
from tqdm import tqdm
import logging
log = logging.getLogger(__name__)


__version__ = 0.11
__date__ = '20240919'
__updated__ = '20240919'
fheader, tail = os.path.split(inspect.stack()[0][1])
__pyfile__ = tail
__path__ = fheader


# warnings.filterwarnings('ignore', category=Warning, message=' FITSFixedWarning: The WCS transformation has more axes (3) than the image it is associated with (2) [astropy.wcs.wcs]', append=True)
warnings.filterwarnings('ignore', category=Warning,
                        message=' FITSFixedWarning: ', append=True)



def lprint(*args, **kwargs):
    
    print(*args, **kwargs)



def simpleDespikeSpectra(spec0, data, hdr, pwidth=10, verbose=False, interpflag=False):
    """Function determining spikes in data array and save the
    spike information in the channel mask / spectra mask.


    Parameters
    ----------
    param1 : int

    Returns
    -------

    """
    if verbose:
        print('Started despiking function.')
    n_spec, n_pix = spec0.shape
    spec = spec0.copy()

    # there is the channel mask already in the table for flagging pixels
    ch_mask = data['CHANNEL_FLAG']
    row_flag = data['ROW_FLAG']
    
    psz = pfr_ra.shape
    if verbose:
        print(psz)

    # this flagging is according to pixel position
    # then replace flux with interpolated value
    for i in range(pp_ra.shape[0]):
        ch_mask[:, pp_ra[i,0]:pp_ra[i,1]] = 1
        if pp_ra[i,0]<pp_ra[i,1]:
            apix = np.arange(pp_ra[i,0]-pwidth, pp_ra[i,1]+pwidth+1, 1)
            if interpflag:
                pargs = apix[(apix<pp_ra[i,0])|(apix>pp_ra[i,1])]
                margs = apix[(apix>=pp_ra[i,0])&(apix<=pp_ra[i,1])]
                for k in trange(0,n_spec):
                    spec[k,pp_ra[i,0]:pp_ra[i,1]+1] = np.interp(margs, pargs, spec[i,pargs])
                    # if np.any(np.isfinite(spec[k,:]))==False:
                    #     print(i, k, spec[k,pp_ra[i,0]-pwidth, pp_ra[i,1]+pwidth+1])

    # for k in trange(0,n_spec):
    #     print(i, k, np.mean(spec[k,:]), np.mean(spec[k,:]))
        
    # try to determine "good" spectra
    # args = range(300, 400)
    # mask = np.ones(n_spec)
    
    # for i in trange(0,n_spec):
    #     sp = spec[i,:]
    #     if np.any(np.isfinite(spec[i,args])):
    #         if np.nanmean(spec[i,args]) > 100.0:
    #             var[i] = (np.nanmax(spec[i,args] - np.nanmin(spec[i,args]))) / np.abs(np.nanmean(spec[i,args]))
    #             if (var[i] < vcut) & (var[i] > 0.0):
    #                 mask[i] = 0    
    #     else:
    #         # there is no valid spectrum
    #         print(i, np.mean(spec[i,args]), spec[i,args])
    #         row_flag[i] = 2

    if verbose:
        print('Done despiking.')
    return spec


def getSpecScanTypes(mixer, spec, data, hdr, verbose=False):
    """Function calculating the calibration spectrum for a single mixer.


    Parameters
    ----------
    mixer : int
        mixer number
    spec : masked float array
        array containing the latest masked spectra
    data : FITS rec array
        record array containing the GUSTO data fron the FITS file

    Returns
    -------

    """

    mixers  = data['MIXER']
    scanID = data['scanID']
    # ra     = data['RA']
    # dec    = data['DEC']
    THOT   = data['THOT']
    scan_type = data['scan_type']
    row_flag = data['ROW_FLAG']      # spectra mask (one entry per spectrum)
    ch_flag = data['CHANNEL_FLAG']   # spectral pixel (or channel) mask

    rfsel = (mixer == mixers) & (scan_type == 'REF') & (row_flag==0)
    rfsID = np.unique(scanID[rfsel])
    rhsel = (mixer == mixers) & (scan_type == 'REFHOT') & (row_flag==0)
    rhsID = np.unique(scanID[rhsel])
    rhsel = (mixer == mixers) & (scan_type == 'REFHOT') & (row_flag==0)
    rhsID = np.unique(scanID[rhsel])

    # identify the HOT spectra
    htsel = (mixer == mixers) & (scan_type == 'HOT') & (row_flag==0)
    hotID = np.unique(scanID[htsel])

    # identify the OTF spectra
    otsel = (mixer == mixers) & (scan_type == 'OTF') & (row_flag==0)
    otfID = np.unique(scanID[otsel])

    # if verbose:
    #     print('Mixer: ', mixer)
    #     print('REF scan IDs: ', rfsID)
    #     print('REFHOT scan IDs: ', rhsID)
    #     print('HOT scan IDs: ', hotID)
    #     print('OTF scan IDs: ', otfID)

    return otfID, rfsID, rhsID, hotID


def getCalSpectra(mixer, spec, data, hdr, Tsky=45., verbose=False):
    """Function calculating the calibration spectrum for a single mixer.


    Parameters
    ----------
    mixer : int
        mixer number
    spec : masked float array
        array containing the latest masked spectra
    data : FITS rec array
        record array containing the GUSTO data fron the FITS file
    Tsky : float
        Sky temperature at wavelength of observation.

    Returns
    -------
    returns averaged noise temperature Tsyss spectra, REFs spectra, RHOTs spectra, 
    and averaged REF and HOT times, rtime and htime, respectively for the spectra 
    before and after the OTF scans. The Tsys time would be the average of rtime 
    and htime for before and after the OTFs.

    """

    mixers  = data['MIXER']
    scanID = data['scanID']
    THOT   = data['THOT']
    scan_type = data['scan_type']
    row_flag = data['ROW_FLAG']      # spectra mask (one entry per spectrum)
    ch_flag = data['CHANNEL_FLAG']   # spectral pixel (or channel) mask
    stime = data['UNIXTIME']

    otfID, rfsID, rhsID, hotID = getSpecScanTypes(mixer, spec, data, hdr, verbose=verbose)
    #if verbose:
    if (len(otfID)<1) & (len(rfsID)<1) & (len(rhsID)<1) & (len(hotID)<1):
        print('Not enough scans types for processing (otf/refs/refhots/hots): ', otfID, rfsID, rhsID, hotID)
        return -999, 0, 0, 0, 0, 0, 0
    
    # determine the REFHOTs that bracket the OTFs
    bef = rhsID[rhsID<otfID]
    aft = rhsID[rhsID>otfID]
    if (len(bef)>0) & (len(aft)>0):
        rhIDbef = bef[np.argmax(bef)]
        rhIDaft = aft[np.argmin(aft)]
    else:
        print('Not enough ref scans available (REFs before/after OTF): ', bef, aft)
        return -999, 0, 0, 0, 0, 0, 0

    rhIDs = [rhIDbef, rhIDaft]

    Tsyss = []
    REFs = []
    RHOTs = []
    ttimes = []
    rtimes = []
    htimes = []
    Thot = []
    for rhID in rhIDs:
        # determine yfactor
        rsel = (rhID == scanID) & (mixer == mixers) & (scan_type == 'REF') & (row_flag==0)
        hsel = (rhID == scanID) & (mixer == mixers) & (scan_type == 'REFHOT') & (row_flag==0)
        #print(rselbef)
    
        spec_h =  spec[hsel,:].sum(axis=0)/len(spec[hsel,:])
        spec_r =  spec[rsel,:].sum(axis=0)/len(spec[rsel,:])
        htime = stime[hsel].mean()
        rtime = stime[rsel].mean()
        #print(list(spec[,:]))
        
        THOT_avg = THOT[hsel].sum(axis=0)/len(THOT[hsel])
        
        # estimate Tsys for each Device
        y_factor  = spec_h/spec_r
        # print('spec_r: ', spec_r)
        # print('y-factor: ', y_factor)
        # if verbose:
        #     print(np.nanmean(spec_h), np.nanmean(spec_r))
        tsys = (THOT_avg - Tsky*y_factor[:])/(y_factor[:] - 1.)
        Thot.append(THOT_avg)
        Tsyss.append(tsys)
        REFs.append(spec_r)
        RHOTs.append(spec_h)
        rtimes.append(rtime)
        htimes.append(htime)

    Tsyss = np.ma.array(Tsyss)
    REFs = np.ma.array(REFs)
    RHOTs = np.ma.array(RHOTs)
    return Tsyss, REFs, RHOTs, rtimes, htimes, Thot, Tsky


    