
from astropy.io import fits 


def history_test(hdr,history_phrase,verbose=False):
    """
    
    test FITS header HISTORY key words or a specfic phrase.
    If phrase exists in header return True,  if no HISTORY or phrase not found return False.
    This test can be used to determine if an application still needs to be run on a FITS product.
    
    """
    if 'HISTORY' not in hdr:
        if verbose: 
            print(f'HISTORY not in {hdr}: {history_phrase} not present')
        return(False)
    else: 
        history_list = hdr.get('HISTORY')
        if f'{history_phrase}' in history_list:
            if verbose: 
                print(f'{history_phrase} present')
            return(True)
        else:
            if verbose:
                print(f'{history_phrase} not found')
            return(False)

