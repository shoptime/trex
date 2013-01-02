import warnings

warnings.simplefilter('default')

def deprecated(f):
    '''
    This is a decorator which can be used to mark functions as deprecated. It
    will result in a warning being emitted when the function is used.
    '''
    def decorated(*args, **kwargs):
        warnings.warn("Call to deprecated function {}.".format(f.__name__), category=DeprecationWarning)
        return f(*args, **kwargs)

    decorated.__name__ = f.__name__
    decorated.__doc__ = f.__doc__
    decorated.__dict__.update(f.__dict__)

    return decorated
