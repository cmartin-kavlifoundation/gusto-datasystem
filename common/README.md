# Utility Definitions 

This directory contains (refactored) code common to more than one 
element of the GUSTO pipeline.  A good example might be code used to 
read or write SDFITS files.


## history_test:  test FITS header HISTORY field 
```
from utility_defs import history_test

bool = history_test(hdr, history_phrase)
```
> **hdr** = FITS header
>
> **history_phrase** = phrase to be found in HISTORY tag.

 * If history_phrase is not present (bool = FALSE),  it can be added.
 * If it is present (bool = TRUE), the processing step has already been done.
