import os
import time
import optparse
import getpass
import datetime
import dateutil
import dateutil.tz
import copy

##################################
# Global Config
##################################

config = None

def setconfig(cls=None):
    """Install the Config and parse."""
    global config
    config = (cls or Config)()
    return config.parse()

def get(key, default=None):
    return config.get(key, default)
    
def set(key, value):
    config.set(key, value)

def db(*args, **kwargs):
    return config.db(*args, **kwargs)
    
def login(*args, **kwargs):
    return config.login(*args, **kwargs)

##################################
# Exported utility methods
##################################

tzlocal = dateutil.tz.gettz()
def gettime():
    return datetime.datetime.now(tzlocal).isoformat()

##################################
# Options
##################################

class Config(object):
    organizationname = "ncmi"
    organizationdomain = "ncmi.bcm.edu"
    applicationname = "EMDash"

    def __init__(self):
        self.defaults = self.set_defaults()
        self.config = {}
        self.store = self.open()
    
    def set_defaults(self):
        import emdash
        defaults = {}
        defaults['film_types'] = ['so-163', 'so163', 'kodak', 'film']
        defaults['starclosed'] = u"\u2605"
        defaults['staropen'] = u"\u2606"
        defaults['sleeptime'] = 5
        defaults['USER_AGENT'] = "emdash %s"%emdash.__version__
        return defaults
        
    def parser(self):
        import argparse
        parser = argparse.ArgumentParser(description=self.applicationname)
        parser.add_argument('--host', '-H', action="store")
        self.defaults['host'] = "http://localhost:8080"
        parser.add_argument('--username', '-U', action="store")
        parser.add_argument('--password', '-P', action="store")
        self.add_options(parser)
        return parser
        
    def add_options(self, parser):
        pass
        
    def parse(self):
        parser = self.parser()
        ns = parser.parse_args()
        self.config.update(vars(ns))
        return ns

    def open(self):
        # QSettings storage backend
        import PyQt4.QtCore
        PyQt4.QtCore.QCoreApplication.setOrganizationName(self.organizationname)
        PyQt4.QtCore.QCoreApplication.setOrganizationDomain(self.organizationdomain)
        PyQt4.QtCore.QCoreApplication.setApplicationName(self.applicationname)      
        return PyQt4.QtCore.QSettings()

    def get(self, key, default=None):
        """Get a value from the current config, or from the config store."""
        value = self.config.get(key)
        if value is not None:
            return value

        if self.store.contains(key):
            import PyQt4.QtCore
            value = self.store.value(key)
            value = unicode(PyQt4.QtCore.QVariant(value).toPyObject())
            self.config[key] = value
            return value

        value = self.defaults.get(key)
        if value is not None:
            self.config[key] = value
            return value

        return default
        
    def set(self, key, value):
        """Set a value in the current config."""
        self.config[key] = value

    def write(self, key, value):
        """Set a value in the config store; this will persist."""
        self.config[key] = value
        self.store.setValue(key, value)

    ##### Create a database handle #####

    def login(self, username=None, password=None):
        db = self.db()
        if username is None:
            username = self.get('username') or raw_input("Email:")
        if password is None:
            password = self.get('password') or getpass.getpass("Password: ")

        # Store the ctxid for other uses.
        ctxid = db.login(username=username, password=password)
        self.set('ctxid', ctxid)
        return db
        
    def db(self, ctxid=None):
        import jsonrpc.proxy
        db = jsonrpc.proxy.JSONRPCProxy(host=self.get('host'))      
        # Awful hack: Set the User-Agent.
        # db._opener.addheaders += [("User-Agent", self.get('USER_AGENT'))]
        ctxid = ctxid or self.get('ctxid')
        if ctxid:
            # Awful hack: set the ctxid.
            db._opener.addheaders += [("Cookie", "ctxid=%s"%ctxid)]
        return db
    
def main():
    opts = setconfig()
    db = config.login()
    return db
    
if __name__ == "__main__":
    db = main()
    