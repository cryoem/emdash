import os
import sys
import dateutil
import shutil
import platform
import logging
from datetime import datetime
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import emdash
import emdash.config
import emdash.handlers

import jsonrpc.proxy
import getpass


REFERENCE_DIRECTORY = "C:\ProgramData\Gatan\Reference Images"
REFERENCE = "K2-0001 1 Gain Ref. x1m3.dm4"
TEM_NAME = "JEOL 3200FSC"


def gettime():
	return datetime.now(dateutil.tz.gettz())


def getmtime(path_to_file):
	md = os.path.getmtime(path_to_file)
	return datetime.fromtimestamp(md,dateutil.tz.gettz())


def printout(msg,level="LOG"):
	sys.stdout.write("{}\t{}\t{}\n".format(gettime(),level,msg))
	sys.stdout.flush()


class Watcher:

	def __init__(self,reference_dir):
		self.cwd = reference_dir
		self.observer = Observer()

	def run(self):
		event_handler = GainRefHandler()
		self.observer.schedule(event_handler, self.cwd, recursive=True)
		self.observer.start()
		try:
			while True: 
				time.sleep(5)
		except:
			self.observer.stop()
		self.observer.join()
		

class GainRefHandler(FileSystemEventHandler):

	def on_any_event(self,event):
		global REFERENCE
		global TEM_NAME
		if event.src_path.split(os.sep)[-1] == REFERENCE:
			if event.event_type in ['created','modified']:
				do_upload()


class AttachmentHandler(emdash.handlers.FileHandler):

	def upload(self,ctxid,host='https://ncmidb.bcm.edu'):
		path = '/record/%s/edit'%(self.target)
		rec = {
			'_format':'json',
			'ctxid':ctxid,
			'file_binary_image': emdash.transport.UploadFile(self.name, 'rb')
		}
		rec = self._upload_put(path,rec)


def do_upload(path=REFERENCE_DIRECTORY,ref=REFERENCE,tem=TEM_NAME):

	printout("Logging in")

	db = jsonrpc.proxy.JSONRPCProxy("http://ncmidb.bcm.edu")
	ctxid = db.login("pi@raspberrypi", "raspberry")

	printout("Uploading...")

	microscope_records = {tem:131}
	microscope = db.record.get(microscope_records['JEOL 3200FSC'])

	abspath = "{}{}{}".format(path,os.sep,ref)

	rec = {}
	rec[u'parents'] = microscope['name']
	rec[u'groups'] = microscope['groups']
	rec[u'permissions'] = microscope['permissions']
	rec[u'rectype'] = "gainref"
	rec[u'date_occurred'] = getmtime(abspath)
	rec.update()

	record = db.record.put(rec)

	# Attach file
	handler = AttachmentHandler()
	handler.target = record.get('name')
	handler.name = abspath
	handler.upload(ctxid)

	printout("Record uploaded successfully!")

	return


def main():

	emdash.config.setconfig()
	emdash.config.set("host","https://ncmidb.bcm.edu")

	global REFERENCE_DIRECTORY

	w = Watcher(REFERENCE_DIRECTORY)
	w.run()


if __name__ == "__main__":
	main()
