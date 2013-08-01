import traceback

##### Logging #####
listeners = []

def add_listener(func):
    listeners.append(func)

def msg(*msg, **kwargs):
    if msg:
        print ' '.join(map(unicode, msg))
    for listener in listeners:
        listener(*msg, **kwargs)

def error(*msg, **kwargs):
    msg = ' '.join(map(unicode, msg))
    print "*****", msg, "*****"
    exception = kwargs.pop('exception', None)
    if exception:
        traceback.print_exc()

