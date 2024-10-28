
from astropy.io import fits 


def history_test(hdr,history_phrase,verbose=False):
    """
    
    test FITS header history key words or a specfic phrase.
    If phrase exists in header return True,  if no HISTORY or phrase not found return False.
    
    """
    if 'HISTORY' not in hdr:
        if verbose: 
            print(f'HISTORY not in {hdr}: Applying {history_phrase}')
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

