#!/usr/bin/env python

from sense_hat import SenseHat
from datetime import datetime
import os
import numpy as np

def main():
    sense = EMSenseHat()
    sense.clear()
    
    date = datetime.now()
    last = {}
    last["second"] = int(date.second)
    last["minute"] = int(date.minute)
    last["hour"] = int(date.hour)
    last["day"] = int(date.day)
    
    fn = "/home/pi/SenseLogs/{}.csv".format(date.date())
    log = EMSenseLog(fn)
    
    high_temp = 30  # display a visual alert if temperature higher than this
    high_humid = 55	# display a visual alert if humidity higher than this
    
    samples = []

    try:
		while True:
			date = datetime.now()
			data = sense.readout()
			samples.append(data)

			if int(date.minute) != last["minute"]:
				avg = np.mean(samples,axis=0)
				log.write(avg)
				
				last["minute"] = int(date.minute)
				to_average = []

				if avg[0] > high_temp:
					sense.high_temp_alert(avg[0])
				if avg[1] > high_humid:
					sense.high_humid_alert(avg[1])
						
			if int(date.second) != last["second"]:
				sense.update_display()

			if int(date.day) != last["day"]:	
				today = log.read()
				maxima = np.max(today,axis=0)
				minima = np.min(today,axis=0)
				average = np.mean(today,axis=0)
				
				
				
				log.erase() # remove old log
				
				fn = "/home/pi/SenseLogs/{}.csv".format(date.date())
				log = EMSenseLog(fn) # create new log
				
				last["day"] = int(date.day)

    except KeyboardInterrupt:
        sense.clear()


class EMSenseLog:
	
	def __init__(self,filename):
		self.filename = filename
		header = ["Timestamp","Temperature","Humidity","Pressure"]
		if not os.path.isfile(self.filename):
			with open(self.filename,"w") as f:
				f.write("#{}\n".format(",".join(header)))
	
	def write(self,data):
		n = datetime.now()
		timestamp = "{} {}:{:02}".format(n.date(),n.hour,n.minute)
		with open(self.filename,"a") as f:
			line = ",".join([str(round(val,1)) for val in data])
			f.write("{},{}\n".format(timestamp,line))
	
	def erase(self):
		os.unlink(self.filename)

	def tail(self):
		with open(self.filename) as f:
			for l in f:
				pass
		return l.strip()
	
	def read(self):
		lines = []
		with open(self.filename,"r") as f:
			for i,l in enumerate(f):
				if i > 0: # skip header and timestamp
					thp = l.strip().split(",")[1:]
					lines.append(thp)
		return np.asarray(lines).astype(float)
		
	def upload(self):
		print("PLACEHOLDER")
		# get max/min temp, humidity, pressure from csv
		# set "environment" protocol
		# specify "this" microscope
		# upload params (humidity, temperature, pressure, date
		# upload csv file
		print("NOT YET IMPLEMENTED")


class EMSenseHat(SenseHat):

	ON_H_PIXEL=[0,0,200]
	ON_T_PIXEL=[200,0,0]
	OFF_PIXEL=[0,0,0]

	high_temp = 50
	low_temp = high_temp - 32

	def readout(self,rnd=1):
		T = round(self.temperature,rnd)
		H = round(self.humidity,rnd)
		P = (self.pressure-1000.)*(255./100.)
		P = round(P,rnd)
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
		self.show_message("HIGH HUMIDITY: {}%".format(round(value,0)),text_colour=self.ON_H_PIXEL)

	def high_temp_alert(self,value):
		self.show_message("ALERT!")
		self.show_message("HIGH TEMP: {}C".format(round(value,0)),text_colour=self.ON_T_PIXEL)

if __name__ == "__main__":
	main()

