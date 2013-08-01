import glob
import optparse
import os
import re
import sys
import time

# emdash imports
import emdash.config
import emdash.handlers
import emdash.emhandlers

class DownloadConfig(emdash.config.Config):
    applicationname = "EMDash"
    def add_options(self, parser):
        parser.add_argument("--recurse", type=int, help="Recursion level", default=-1)
        parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files (default is to skip)", default=False)
        parser.add_argument("--rename", action="store_true", help="Rename files to the BDO name (e.g. bdo.201202020000.dm3)", default=False)
        parser.add_argument("--nogzip", action="store_true", help="Do not decompress files", default=False)
        parser.add_argument('names', metavar='names', nargs='+', help='Record names')


class UploadConfig(emdash.config.Config):
    applicationname = "EMDash"
    def add_options(self, parser):
        parser.add_argument("--handler", help="Handler; examples: ccd, ddd, stack")
        parser.add_argument("--rectype", help="Set rectype on handler.")
        parser.add_argument("--param", help="Set param on handler.")
        parser.add_argument('target', metavar='target', nargs=1, help='Target record')
        parser.add_argument('names', metavar='names', nargs='+', help='Record names')

def download():
    # Parse arguments
    ns = emdash.config.setconfig(DownloadConfig)
    names = vars(ns).get('names', [])
    recurse = ns.recurse

    # Login
    emdash.config.login()
    ctxid = emdash.config.get('ctxid')
    host = emdash.config.get('host')
    
    # Download
    bdos = []
    for name in names:
        if recurse != 0:
            recs = [name]
            recs += emdash.config.db().rel.children(name, recurse=recurse)
        else:
            recs = [name]
        print "Found recs:", len(recs)
        bdos = emdash.config.db().binary.find(record=recs, count=0)
        print "Found bdos:", len(bdos)

    for bdo in bdos:
        uri = '%s/download/%s/%s?ctxid=%s'%(host, bdo.get('name'), bdo.get('filename'), ctxid)
        dbt = emdash.handlers.FileHandler(name=bdo.get('name'), data=bdo)
        dbt.download()
        
def upload():
    # Parse arguments
    ns = emdash.config.setconfig(UploadConfig)
    names = vars(ns).get('names', [])

    # Login
    emdash.config.login()
    ctxid = emdash.config.get('ctxid')
    host = emdash.config.get('host')
    
    # Upload
    for name in names:
        dbt = emdash.handlers.get_handler(ns.handler)
        dbt.target = ns.target[0]
        dbt.name = name
        if ns.rectype:
            dbt.rectype = ns.rectype
        if ns.param:
            dbt.param = ns.param
        dbt.upload()
