#
#
import os
import glob
import math
import random
import numpy as np
import configparser
from scipy import interpolate

from pathlib import Path

from astropy import units as u

from astropy.io import fits
from astropy.io.fits import Header
from astropy.table import Table

from pybaselines import Baseline



################################################################################
def doStuff(self):
   my_file = Path(self)
   try:
       my_file.resolve(strict=True)
   except FileNotFoundError:
       print("file not found ", end="")
       return None
   else:
       hdu    = fits.open(self)

   header = hdu[1].header
   data   = hdu[1].data
   spec   = data['DATA']
   n_OTF  = len(data)
   x = np.arange(1024)

   crval2 = header['CRVAL2']   # reference RA pixel
   crval3 = header['CRVAL3']   # reference DEC pixel

   cdelt2 = hdu[1].data['CDELT2']   # array of RA offsets
   cdelt3 = hdu[1].data['CDELT3']   # array of DEC offsets

   xlow   = 100
   xhigh  = 250
   base = np.zeros([n_OTF,xhigh-xlow])
   baseline_fitter = Baseline(x_data=x[xlow:xhigh])
   y_flat = np.zeros(xhigh-xlow)

   ii=np.zeros(n_OTF)
   l=np.zeros(n_OTF)
   b=np.zeros(n_OTF)
   for i in range(n_OTF):
      spec_to_draw = spec[i,xlow:xhigh] - np.median(spec[i,xlow:xhigh])
      spec_new = spec_to_draw - base[i,0:(xhigh-xlow)]
      base2 = baseline_fitter.aspls(spec_new, 1e5)
      y_flat = spec_new - base2[0]
      ii[i] = sum(y_flat)
      l[i] = crval2 + cdelt2[i]
      b[i] = crval3 + cdelt3[i]

   # Return the (l,b) position and integrated intensity
   data = (l, b, ii)
   return data


def regrid(l, b, T, beam):
   # Calculate the range of ra and dec values
   l_min, l_max = np.min(l), np.max(l)
   b_min, b_max = np.min(b), np.max(b)

   # Calculate number of grid points
   N_l = int(np.ceil((l_max - l_min) / beam))
   N_b = int(np.ceil((b_max - b_min) / beam))
   print(N_ra)
   print(N_dec)

   # Create meshgrid
   l_grid, b_grid = np.meshgrid(np.linspace(l_min, l_max, N_l),np.linspace(b_min, b_max, N_b))

   # Initialize array
   avg_T = interpolate.griddata((l, b), T, (l_grid, b_grid), method='nearest')

   return l_grid, b_grid, avg_T


def get_filenames(directory, scan_file):
    # Read filenames from text file generated by findSCANS.py
    with open(scan_file, 'r') as file:
        filenames = [line.strip() for line in file]

    fullpath = [os.path.join(directory, filename) for filename in filenames]

    return fullpath


################################################################################



# ConfigParser Object
config = configparser.ConfigParser()

# Read config file for Data Paths
config.read('config.ini')
paths=[]
paths.append(config.get('Paths', 'B1_path'))
paths.append(config.get('Paths', 'B2_path'))

#partial = sys.argv[1]
#search_files=[]
#for path in paths:
#   search_files+=sorted(glob.glob(f"{path}/{partial}.fits"))


search_files=[]
search_files =get_filenames(paths[1], 'acs3-scans.txt')
search_files+=get_filenames(paths[0], 'acs5-scans.txt')

# Debug
#print("\n".join(search_files))


# Initialize empty lists to accumulate data
ra_list = []
dec_list = []
Ta_list = []

for file in search_files:
    # get ra, dec, and calibrated spectra from each OTF file
    print("trying OTF file: ", file)

    result = doStuff(file)

    if result is None:
        print("nothing returned")
    else:
        (ra, dec, Ta) = result

        ra_list.append(ra)
        dec_list.append(dec)
        Ta_list.append(Ta)

# Convert lists to numpy arrays
ra  = np.array(ra_list)
dec = np.array(dec_list)
Ta  = np.array(Ta_list)


# open a new blank FITS file
hdr = fits.Header()
hdr['NAXIS']   = 2
hdr['DATAMIN'] = min(Ta)
hdr['DATAMAX'] = max(Ta)
hdr['BUNIT']   = 'K (Ta*)     '

hdr['CTYPE1']  = 'RA          '
hdr['CRVAL1']  = min(ra)
hdr['CDELT1']  = 0.016              # 1 arcmin beam
hdr['CRPIX1']  = 0                  # reference pixel array index
hdr['CROTA1']  = 0
hdr['CUNIT1']  = 'deg         '

hdr['CTYPE2']  = 'DEC         '
hdr['CRVAL2']  = min(dec)
hdr['CDELT2']  = 0.016              # 1 arcmin beam
hdr['CRPIX2']  = 0                  # reference pixel array index
hdr['CROTA2']  = 0
hdr['CUNIT2']  = 'deg         '

hdr['OBJECT']  = 'NGC6334     '
hdr['RADESYS'] = 'FK5         '
hdr['RA']      = min(ra)            # Fiducial is arbitrarily (ra,dec) min
hdr['DEC']     = min(dec)
hdr['EQUINOX'] = 2000
hdr['LINE']    = 'C+          '
hdr['RESTFREQ']= 1900.5369          # GHz
hdr['VELOCITY']= 0

# Do the regridding
ra_grid, dec_grid, T_img= regrid(ra, dec, Ta, 0.02)

# Write the data cube and header to a FITS file
#hdu = fits.PrimaryHDU(data=T_img, header=hdr)
#hdu.writeto('my_data_image.fits', overwrite=True)



