#!/usr/bin/env python

from sense_hat import SenseHat
from datetime import datetime
import os
import sys
import numpy as np
import time
import dateutil
import dateutil.tz

import emdash.config
import emdash.handlers

def gettime():
    return datetime.now(dateutil.tz.gettz())

def main():
	ns = emdash.config.setconfig()
	config = emdash.config.Config()
	
	this = gettime()
	print("Init: {}".format(this))
	print("Host: {}".format(config.get("host")))
	print("User: {}".format(config.get("username")))
	print("Protocol: {}".format(config.get("session_protocol")))

	db = config.db()
	ctxid = db.login(config.get("username"),config.get("password"))
	
	emdash.config.set("ctxid",ctxid)
	print("CTXID: {}".format(ctxid))
	
	suite = db.record.get(config.get("suite"))
	print("Record #{}".format(config.get("suite")))
	print("Name: {}".format(suite["suite_name"]))
	
	sys.stdout.flush()

	sense = EMSenseHat()
	sense.clear()
		
	last = {}
	last["second"] = int(this.second)
	last["minute"] = int(this.minute)
	last["hour"] = int(this.hour)
	last["day"] = int(this.day)

	high_temp = 25.  # alert if temperature > this
	high_humid = 45. # alert if humidity > this

	samples = []

	log = EMSensorLog(config)
	
	while True:
		this = gettime()
		
		# Every second
		if this.second != last["second"]:
			data = sense.readout()
			samples.append(data)
			sense.update_display()
			last["second"] = this.second
					
		# Every minute
		if this.minute != last["minute"]:
			avg = np.mean(samples,axis=0)
			log.write(avg)
			samples = []
			last["minute"] = this.minute
				
		# Every hour
		if this.hour != last["hour"]:
			if rec["temperature_ambient_avg"] > high_temp:
				sense.high_temp_alert(rec["temperature_ambient_avg"])
			if rec["humidity_ambient_avg"] > high_humid:
				sense.high_humid_alert(rec["humidity_ambient_avg"])
			last["hour"] = this.hour
		
		# Every day
		if this.day != last["day"]:
			rec = log.upload(db)
			last["day"] = this.day

class EMSensorLog:

	def __init__(self,conf):
		self.start_date = gettime()
		self.csv_file = CSVHandler()
		self.csv_file.name = "/home/pi/logs/{}.csv".format(self.start_date.date())
		self.csv_file.header = ["timestamp","temperature","humidity","pressure"]
		if not os.path.isfile(self.csv_file.name):
			with open(self.csv_file.name,"w") as f:
				f.write("#{}\n".format(",".join(self.csv_file.header)))

	def write(self,data,rnd=1):
		n = gettime()
		with open(self.csv_file.name,"a") as f:
			dat = ",".join([str(round(val,rnd)) for val in data])
			out = "{},{}\n".format(n,dat)
			f.write(out)
	
	def read(self):
		data = []
		with open(self.csv_file.name,"r") as f:
			for i,l in enumerate(f):
				if i > 0: # skip header
					line = l.strip().split(",")
					data.append(line[1:])
		return np.asarray(data).astype(float)
	
	def upload(self,db):
		self.end_date = gettime()
		data = self.read()
		
		t_high,h_high,p_high = np.max(data,axis=0)
		t_low,h_low,p_low = np.min(data,axis=0)
		t_avg,h_avg,p_avg = np.mean(data,axis=0)
		
		config = emdash.config.Config()
		suite = db.record.get(config.get("suite"))
		
		rec = {}
		rec['parents'] = suite['name']
		rec['groups'] = suite['groups']
		rec['permissions'] = suite['permissions']
		rec['rectype'] = config.get("session_protocol")
		rec["date_start_dt"] = self.start_date.isoformat()
		rec["date_end_dt"] = self.end_date.isoformat()
		rec["temperature_ambient_low"] = round(t_low,1)
		rec["temperature_ambient_high"] = round(t_high,1)
		rec["temperature_ambient_avg"] = round(t_avg,1)
		rec["humidity_ambient_low"] = round(h_low,1)
		rec["humidity_ambient_high_float"] = round(h_high,1)
		rec["humidity_ambient_avg"] = round(h_avg,1)
		rec["pressure_ambient_low"] = round(p_low,1)
		rec["pressure_ambient_high"] = round(p_high,1)
		rec["pressure_ambient_avg"] = round(p_avg,1)
		rec["comments"] = ""
		
		record = db.record.put(rec)
		
		self.csv_file.target = record["name"]
		self.csv_file.rectype = config.get("session_protocol")
		self.csv_file.data = record
		
		record = self.csv_file.upload()
		
		try: # remove local file after upload is complete
			os.unlink(self.csv_file.name)
		except:
			n = gettime()
			print("{}\tWARNING: Failed to remove {}".format(n,self.csv_file.name))
			sys.stdout.flush()
		
		self.csv_file.name = "/home/pi/logs/{}.csv".format(self.end_date.date())
		self.start_date = gettime()
		
		return record

class EMSenseHat(SenseHat):

	ON_H_PIXEL=[0,0,255]
	ON_T_PIXEL=[255,0,0]
	OFF_PIXEL=[0,0,0]

	high_temp = 37.7
	low_temp = 0.

	def readout(self,rnd=1):
		T = round(self.temperature,rnd)
		H = round(self.humidity,rnd)
		P = round(self.pressure,rnd)
		return [T,H,P]

	def update_display(self):
		pixels = []
		h_on_count = int(32*(self.humidity/100.))
		h_off_count = 32-h_on_count
		pixels.extend([self.ON_H_PIXEL] * h_on_count)
		pixels.extend([self.OFF_PIXEL] * h_off_count)
		norm_temp = (self.high_temp-self.temp)/(self.high_temp-self.low_temp)
		t_on_count = int(32*(norm_temp))
		t_off_count = 32-t_on_count
		pixels.extend([self.ON_T_PIXEL] * t_on_count)
		pixels.extend([self.OFF_PIXEL] * t_off_count)
		self.set_pixels(pixels)

	def high_humid_alert(self,value):
		self.show_message("ALERT!")
		self.show_message("HIGH HUMIDITY: {:0.0f}%".format(value),text_colour=self.ON_H_PIXEL)

	def high_temp_alert(self,value):
		self.show_message("ALERT!")
		self.show_message("HIGH TEMP: {:0.0f}C".format(value),text_colour=self.ON_T_PIXEL)

class CSVHandler(emdash.handlers.FileHandler):

    def upload(self):
        self.log("\n--- Starting upload: %s ---"%self.name)

		# Check JSON
        check = self.sidecar_read(self.name)
        if check.get('name'):
            self.log("File already exists in database -- check %s"%check.get('name'))
            return check

        # This upload method will always create a new record for each file.
        target = self.target or self.data.get('_target')

        # New record request
        qs = {}
        qs['_format'] = 'csv'
        qs['ctxid'] = emdash.config.get('ctxid')
        qs['date_occurred'] = emdash.handlers.filetime(self.name)
        
        for k,v in self.data.items():
            if not k.startswith('_'):
                qs[k] = v
        
        # File to upload
        qs[self.param] = open(self.name, "rb")

        # Extract metadata...
        qs.update(self.extract())
        
        # Try to upload. Creates a new record.
        path = '/record/%s/new/%s/'%(target, self.rectype)
		
        # ... default is PUT -- much faster, less memory.
        rec = self._upload_put(path, qs)

        # Write out the sidecar file.
        self.sidecar_write(self.name, {"name":rec.get('name')})

        # Return the updated (or new) record..
        return rec

if __name__ == "__main__":
	main()
