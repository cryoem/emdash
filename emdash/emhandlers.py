import collections
import copy
import glob
import math
import os
import struct
import subprocess
import tempfile
import time
import httplib
import urllib
import urllib2
import socket
import json
import glob

import datetime
import dateutil
import dateutil.tz

# XML Etree
try:
    import xml.etree.ElementTree as ET
except ImportError:
    ET = None

# EMDash imports
import emdash.config
import emdash.log
import emdash.transport
from emdash.handlers import Handler, FileHandler

# EMAN2 can only be IMPORTED BY MAIN THREAD.
try:
    import EMAN2
except Exception, e:
    emdash.log.error("Couldn't load EMAN2", exception=e)
    EMAN2 = None


def sign(a):
    if a>0: return 1
    return -1

##### Read EMAN2 Files! #####

class EMDataReader(object):
    
    # Known EMData Header Parameters
    emdata_params = set([
        'dm3_acq_date',
        'dm3_acq_time',
        'dm3_actual_mag',
        'dm3_antiblooming',
        'dm3_binning_x',
        'dm3_binning_y',
        'dm3_camera_x',
        'dm3_camera_y',
        'dm3_cs',
        'dm3_exposure_number',
        'dm3_exposure_time',
        'dm3_frame_type',
        'dm3_indicated_mag',
        'dm3_name',
        'dm3_pixel_size',
        'dm3_source',
        'dm3_voltage',
        'dm3_zoom',
        'emdata_apix_x',
        'emdata_apix_y',
        'emdata_apix_z',
        'emdata_changecount',
        'emdata_class_id',
        'emdata_class_ptcl_idxs',
        'emdata_class_ptcl_src',
        'emdata_ctf_phase_flipped',
        'emdata_ctf_snr_total',
        'emdata_ctf_wiener_filtered',
        'emdata_data_n',
        'emdata_data_path',
        'emdata_data_source',
        'emdata_datatype',
        'emdata_eigval',
        'emdata_exc_class_ptcl_idxs',
        'emdata_hostendian',
        'emdata_is_complex',
        'emdata_is_complex_ri',
        'emdata_kurtosis',
        'emdata_match_n',
        'emdata_match_qual',
        'emdata_maximum',
        'emdata_mean',
        'emdata_mean_nonzero',
        'emdata_median',
        'emdata_microscope_cs',
        'emdata_microscope_voltage',
        'emdata_minimum',
        'emdata_model_id',
        'emdata_nonzero_median',
        'emdata_nx',
        'emdata_ny',
        'emdata_nz',
        'emdata_origin_x',
        'emdata_origin_y',
        'emdata_origin_z',
        'emdata_projection_image',
        'emdata_projection_image_idx',
        'emdata_ptcl_helix_coords',
        'emdata_ptcl_repr',
        'emdata_ptcl_source_coord',
        'emdata_ptcl_source_image',
        'emdata_reconstruct_norm',
        'emdata_reconstruct_preproc',
        'emdata_reconstruct_qual',
        'emdata_render_max',
        'emdata_render_min',
        'emdata_segment_centers',
        'emdata_sigma',
        'emdata_sigma_nonzero',
        'emdata_skewness',
        'emdata_source_n',
        'emdata_source_path',
        'emdata_square_sum',
        'emdata_subvolume_full_nx',
        'emdata_subvolume_full_ny',
        'emdata_subvolume_full_nz',
        'emdata_subvolume_x0',
        'emdata_subvolume_y0',
        'emdata_subvolume_z0',
        'emdata_threed_excl_ptcl_idxs',
        'emdata_threed_ptcl_idxs',
        'emdata_threed_ptcl_src',
        'imagic_count',
        'imagic_error',
        'imagic_headrec',
        'imagic_hour',
        'imagic_imgnum',
        'imagic_ixold',
        'imagic_iyold',
        'imagic_label',
        'imagic_mday',
        'imagic_minute',
        'imagic_month',
        'imagic_oldav',
        'imagic_pixels',
        'imagic_reals',
        'imagic_sec',
        'imagic_type',
        'imagic_year',
        'mrc_alpha',
        'mrc_beta',
        'mrc_gamma',
        'mrc_ispg',
        'mrc_machinestamp',
        'mrc_mapc',
        'mrc_mapr',
        'mrc_maps',
        'mrc_maximum',
        'mrc_mean',
        'mrc_minimum',
        'mrc_mx',
        'mrc_my',
        'mrc_mz',
        'mrc_nlabels',
        'mrc_nsymbt',
        'mrc_nx',
        'mrc_nxstart',
        'mrc_ny',
        'mrc_nystart',
        'mrc_nz',
        'mrc_nzstart',
        'mrc_rms',
        'mrc_xlen',
        'mrc_ylen',
        'mrc_zlen',
        'serialem_tilt_angle',
        'serialem_tilt_dose',
        'serialem_tilt_intensity',
        'serialem_tilt_magnification',
        'serialem_tilt_montage',
        'serialem_tilts_angle',
        'serialem_tilts_dose',
        'serialem_tilts_magnification',
        'spider_angvalid',
        'spider_date',
        'spider_dx',
        'spider_dy',
        'spider_dz',
        'spider_gamma',
        'spider_headlen',
        'spider_headrec',
        'spider_imgnum',
        'spider_irec',
        'spider_istack',
        'spider_k_angle',
        'spider_maxim',
        'spider_nslice',
        'spider_phi',
        'spider_phi1',
        'spider_phi2',
        'spider_psi1',
        'spider_psi2',
        'spider_reclen',
        'spider_scale',
        'spider_theta',
        'spider_theta1',
        'spider_theta2',
        'spider_time',
        'spider_title',
        'spider_type',
        'tiff_bitspersample',
        'tiff_resolution_x',
        'tiff_resolution_y'
    ])    
    
    def __init__(self, filename):
        self.filename = filename

    def emdata_header(self):
        """Get header information from EMAN2."""
        if not EMAN2:
            return
                
        # EMAN2 only works with str filenames; no unicode.
        img = EMAN2.EMData()
        img.read_image(str(self.filename), 0, True)
        header = img.get_attr_dict()
        return header

    def emdata_rename(self, header):
        '''Convert EMData attributes to EMEN2 parameter names.'''
        ret = {}
        prefixes = ['mrc', 'dm3', 'tiff', 'imagic', 'spider']
        mrclabels = []
    
        for k,v in header.items():
            if k.startswith('MRC.label'):
                mrclabels.append(v)
                continue
        
            # Rename the key
            pre, _, post = k.rpartition(".")
            pre = pre or "emdata"
            k = '%s_%s'%(pre.lower(), post)
            if k in self.emdata_params:
                ret[k] = v
            # else:
            #    print "Skipping unknown EMData key:", k

        if mrclabels:
            ret['mrc_label'] = mrclabels

        # Remove the source path; it will just point to a tmp file.
        ret.pop('emdata_source_path', None)
        return ret

##### Cryo-EM Specific File Handlers #####

@Handler.register('ccd')
class CCDHandler(FileHandler):
    rectype = "ccd"
    param = "file_binary_image"
    exts = ['.dm3', '.tif', '.tiff', '.hdf5', '.h5', '.hdf', '.mrc']
    
    def extract(self):
        # Extract the header
        reader = EMDataReader(self.name)
        header = reader.emdata_header()
        # Rename the header keys
        header = reader.emdata_rename(header)
        return header


@Handler.register('ddd_tif')
class CCDHandler(FileHandler):
    rectype = "ddd"
    param = "ddd_binary_final"
    exts = ['.tif', '.tiff']
    
    def extract(self):
        # Extract the header
        reader = EMDataReader(self.name)
        header = reader.emdata_header()
        # Rename the header keys
        header = reader.emdata_rename(header)
        return header
                
@Handler.register('ddd_raw')
@Handler.register('ddd')
class DDDHandler(FileHandler):
    rectype = "ddd"
    
    # Map DDD "info.txt" parameters to EMEN2 parameters.
    ddd_mapping = {
        'Binning X': 'binning_x',
        'Binning Y': 'binning_y',
        'Camera Position': 'camera_position',
        'Dark Correction': 'ddd_dark_correction',
        'Dark Frame Status': 'ddd_dark_frame_status',
        'Data Output Mode': 'ddd_data_output_mode',
        'Exposure Mode': 'ddd_exposure_mode',
        'FPGA Version': 'ddd_fpga_version',
        'Faraday Plate Peak Reading During Last Exposure': 'faraday_plate_peak',
        'Gain Correction': 'ddd_gain_correction',
        'Gain Frame Status': 'ddd_gain_frame_status',
        'Hardware Binning X': 'binning_hardware_x',
        'Hardware Binning Y': 'binning_hardware_y',
        'Last Dark Frame Dataset': 'ddd_last_dark_frame_dataset',
        'Last Gain Frame Dataset': 'ddd_last_gain_frame_dataset',
        'Preexposure Time in Seconds': 'time_preexposure',
        'ROI Offset H': 'roi_offset_h',
        'ROI Offset W': 'roi_offset_w',
        'ROI Offset X': 'roi_offset_x',
        'ROI Offset Y': 'roi_offset_y',
        'Raw Frames Filename Suffix': 'ddd_raw_frame_suffix',
        'Raw Frames Type': 'ddd_raw_frame_type',
        'Save Raw Frames': 'ddd_raw_frame_save',
        'Save Summed Image': 'ddd_raw_frame_save_summed',
        'Screen Position': 'screen_position',
        'Sensor Coarse Gain': 'ddd_sensor_coarse_gain',
        'Sensor Offset': 'ddd_sensor_offset',
        'Sensor Output Mode': 'ddd_sensor_output_mode',
        'Temperature Cold Finger (Celsius)': 'ddd_temperature_cold_finger',
        'Temperature Control': 'ddd_temperature_control',
        'Temperature Control Mode': 'ddd_temperature_control_mode',
        'Temperature Detector (Celsius)': 'ddd_temperature_detector',
        'Temperature TEC Current (Ampere)': 'ddd_temperature_tec_current',
        'Temperature Water Line (Celsius)': 'ddd_temperature_water_line',
        'Vacuum Level': 'vacuum_level'
    }
    
    def check(self, item):
        # Presence of an "info.txt" file signifies the directory contains DDD frames.
        if os.path.basename(item) == "info.txt":
            return item

    def display_name(self):
        # Display just the directory name.
        return os.path.basename(os.path.dirname(self.name))

    def upload(self):
        self.log("\n--- Starting upload: %s ---"%self.name)
        self.log("Checking for previously uploaded files...")
        
        # Check JSON. First, look if info.txt is uploaded. Then, check raw frames.
        check = self.sidecar_read(self.name)
        if check.get('name'):
            self.log("Already exists in database -- check %s"%check.get('name'))
            # Try to upload raw frames that weren't already uploaded.
            self.upload_raw_hdf(check.get('name'))
            return check

        # Wait a small amount of time before completing (default=0)
        if self.wait:
            self.log("Waiting %s seconds before proceeding"%self.wait)
            time.sleep(self.wait)

        # Upload target.
        target = self.data.get('_target')

        # New record request.
        qs = {}
        # Return format. 
        qs['_format'] = 'json' 
        qs['ctxid'] = emdash.config.get('ctxid')
        # Set the date_occurred parameter to the file's timestamp.
        qs['date_occurred'] = emdash.handlers.filetime(self.name)
        # Include any parameters set via the EMDash UI.
        for k,v in self.data.items():
            if not k.startswith('_'):
                qs[k] = v

        # Parse the info.txt file.
        self.log("Reading metadata...")
        qs.update(self.extract())
        
        # This is used as a "ccd frame name" in some places.
        qs['id_ccd_frame'] = os.path.basename(os.path.dirname(self.name))
        name_prefix = os.path.basename(os.path.dirname(self.name))+'_'

        # Info file.
        qs['ddd_binary_info'] = [emdash.transport.UploadFile(self.name, "rb", name_prefix=name_prefix)]        
        # The SumImage file; summed raw frames.
        qs['ddd_binary_sum'] = [emdash.transport.UploadFile(i, 'rb', name_prefix=name_prefix) for i in self.find('SumImage')]
        # The FinalImage file; summed and gain corrected.
        qs['ddd_binary_final'] = [emdash.transport.UploadFile(i, 'rb', name_prefix=name_prefix) for i in self.find('FinalImage')]

        # Collect all the handles to close after upload.
        files = []
        files.extend(qs['ddd_binary_info'])
        files.extend(qs['ddd_binary_sum'])
        files.extend(qs['ddd_binary_final'])
        
        fn = ", ".join([i.name for i in files])
        self.log("Creating a new DDD record and uploading files: %s"%fn)

        # Upload Info.txt, SumImage, and FinalImage as a new DDD record.
        rec = self._upload_post('/record/%s/new/%s/'%(target, self.rectype), qs)

        if rec.get('name') is None:
            raise Exception, "Error uploading! Did not get a record ID!"

        # Close handles and write sidecar files.
        for f in files:
            f.close()
            self.sidecar_write(f.name, {"name":rec.get('name')})

        # Upload the raw HDF to the newly created record.
        self.upload_raw_hdf(rec.get('name'))

        # Return the updated (or new) record..
        return rec

    def upload_raw_hdf(self, target):
        raw_filename = os.path.join(os.path.dirname(self.name), "raw.hdf")
        name_prefix = os.path.basename(os.path.dirname(self.name))+'_'
        
        # Check to see if a raw HDF was already uploaded.
        # The raw HDF file itself may have been removed, and just left the raw.json file.
        check = self.sidecar_read(raw_filename)
        if check.get('name'):
            self.log("Raw HDF exists in database -- check %s"%check.get('name'))
            return check
        
        # Create raw HDF. 
        if os.path.exists(raw_filename):
            self.log("Removing existing raw HDF.")
            os.unlink(raw_filename)
        
        self.create_raw_hdf(raw_filename)
        if not os.path.exists(raw_filename):
            self.log("No raw frames to upload?")
            return

        # Now, try to upload the large (>1GB) raw frames as a single HDF file.
        # We have to use a second PUT request due to memory/speed issues with a single
        # large POST request. Errors are likely when sent as part of the previous POST.
        raw_file = emdash.transport.UploadFile(raw_filename, "rb", name_prefix=name_prefix)
        raw_qs = {
            '_format': 'json',
            'ctxid': emdash.config.get('ctxid'),
            'ddd_binary_raw': raw_file
        }
        self._upload_put('/record/%s/edit/'%(target), raw_qs)
        # Close the file
        raw_file.close()
        self.sidecar_write(raw_filename, {"name":target})
        
        # Remove temporary raw HDF file
        if os.path.exists(raw_filename):
            os.unlink(raw_filename)

    def create_raw_hdf(self, outfile):
        # This is a very expensive process and may take a while.
        # This runs in the main thread :( Blocks the UI. Must fix.
        files = self.find('RawImage')
        if not files:
            return
        self.log("Creating raw HDF with %s frames: %s"%(len(files), outfile))
        outfile = str(outfile)
        # Sort the raw frames
        files = sorted(files, key=lambda x:int(x.split("_")[-1].split(".")[0]))
        for f in files:
            f = str(f)
            self.log("Adding %s to raw HDF"%(os.path.basename(f)))
            e = EMAN2.EMData()
            e.read_image(f)
            e['render_min'] = -1
            e['render_max'] = 256*256
            e.write_image(outfile, -1, EMAN2.EMUtil.ImageType.IMAGE_HDF, False, None, EMAN2.EMUtil.EMDataType.EM_USHORT, False)

    # Find files!
    def find(self, ext):
        # Check files that exist..
        dirname = os.path.dirname(self.name)
        ret = []
        filenames = glob.glob(os.path.join(dirname, "*.tif"))
        for filename in filenames:
            if ext in os.path.basename(filename):
                ret.append(filename)                    
        return ret

    def extract(self):
        f = open(self.name, "rb")
        data = f.readlines()
        f.close()

        ret = {}
        for line in data:
            param, _, value = line.strip().partition("=")
            mapparam = self.ddd_mapping.get(param)
            if mapparam:
                # print 'param %s -> %s: %s'%(param, mapparam, value)
                ret[mapparam] = value

        return ret

@Handler.register('serialem')
class SerialEMHandler(FileHandler):    
    exts = ['.st']
    rectype = "stack"
    param = "file_binary_image"

    # IMOD SerialEM format
    # http://bio3d.colorado.edu/imod/doc/guide.html    
    # Start at a 92 byte offset (standard MRC header attributes)
    # Then read in the following SerialEM Headers.
    # [target parameter, C struct type, default value]
    header_labels = [
        # Number of bytes in extended header
        ['serialem_extheadersize', 'i', 0],
        # Creator ID, creatid
        ['serialem_creatid', 'h', 0],
        # 30 bytes of unused data
        [None, '30s', ''],
        ## Number of bytes per section (SerialEM format) of extended header
        ['serialem_bytespersection', 'h', 0],
        # Flags for which types of short data (SerialEM format), nreal. (See extheader_flags)
        ['serialem_extheaderflags', 'h', 0],
        # 28 bytes of unused data
        [None, '28s', ''],
        # Additional SerialEM attributes
        ['serialem_idtype', 'h', 0],
        ['serialem_lens', 'h', 0],
        ['serialem_nd1', 'h', 0],
        ['serialem_nd2', 'h', 0],
        ['serialem_vd1', 'h', 0],
        ['serialem_vd2', 'h', 0],
        ['serialem_tiltangles_orig', 'fff', [0.0, 0.0, 0.0]],
        ['serialem_tiltangles_current', 'fff', [0.0, 0.0, 0.0]],
        ['serialem_xorg', 'f', 0.0],
        ['serialem_yorg', 'f', 0.0],
        ['serialem_zorg', 'f', 0.0],
        ['serialem_cmap', '4s', '']
    ]

    # The SerialEM extended header is a mask
    # Compare with the following keys to find the attributes
    extheader_flags = {
        1: {'pack': 'h',
            'load': lambda x:[x[0] / 100.0],
            'dump': lambda x:[x[0] * 100],
            'dest':  ['serialem_tilt'],
            'also': ['specimen_tilt']},

        2: {'pack': 'hhh',
            'load': lambda x:[x],
            'dump': lambda x:[x],
            'dest': ['serialem_montage']},

        4: {'pack': 'hh',
            'load': lambda x:[x[0] / 25.0 , x[1] / 25.0],
            'dump': lambda x:[x[0] * 25   , x[1] * 25],
            'dest': ['serialem_stage_x', 'serialem_stage_y'],
            'also': ['position_stage_x', 'position_stage_y']},

        8: {'pack': 'h',
            'load': lambda x:[x[0] / 10.0],
            'dump': lambda x:[x[0] * 10],
            'dest': ['serialem_magnification'],
            'also': ['tem_magnification_set']},

        16: {'pack': 'h',
            'load': lambda x:[x[0] / 25000.0],
            'dump': lambda x:[x[0] * 25000],
            'dest': ['serialem_intensity']},

        32: {'pack': 'hh',
            'load': lambda x:[sign(x[0])*(math.fabs(x[0])*256+(math.fabs(x[1])%256))*2**(sign(x[1])*(int(math.fabs(x[1]))/256))],
            'dump': lambda x:[0,0],
            'dest': ['serialem_dose']}
    }

    def auto_enqueue(self):
        return False
    
    ##### Read SerialEM extended header #####

    def extract(self):
        reader = EMDataReader(self.name)
        header = reader.emdata_header()

        # ... get the extheader information
        try:
            serialem_header = self._get_serielem_header(self.name)
        except:
            serialem_header = {}
        header.update(serialem_header)

        # ... get the extheader values
        try:                
            extheader = self._get_serialem_extheader(self.name, header['serialem_extheadersize'], header['nz'], header['serialem_extheaderflags'])
        except:
            extheader = {}
        header.update(extheader)

        # ... just include the min and max angles ...
        tilts = filter(lambda x:x!=None, [i.get('serialem_tilt') for i in extheader])
        if tilts:
            header["serialem_maxangle"] = max(tilts)
            header["serialem_minangle"] = min(tilts)
    
        # Rename
        header = reader.emdata_rename(header)
        return header

    def _get_serielem_header(self, workfile, offset=92):
        """Extract data from header string (1024 bytes) and process"""
        f = open(workfile,"rb")
        hdata = f.read(1024)
        f.close()
        
        d={}
        for dest, format, default in self.header_labels:
            size = struct.calcsize(format)
            value = struct.unpack(format, hdata[offset:offset+size])
            if dest == None:
                pass
            elif len(value) == 1:
                d[dest] = value[0]
            else:
                d[dest] = value
            offset += size
        return d

    def _get_serielem_extheader(self, workfile, serialem_extheadersize, nz, flags):
        """Process extended header"""

        f = open(workfile,"rb")
        hdata = f.read(1024)
        ehdata = f.read(serialem_extheadersize)
        f.close()

        ed = []
        offset = 0

        # Get the extended header attributes
        keys = self._extheader_getkeys(flags)

        # For each slice..
        for i in range(0, nz):
            sslice = {}

            # Process each extended header attribute
            for key in keys:
                # Get the flags and calculate the size
                parser = self.extheader_flags.get(key)
                size = struct.calcsize(parser['pack'])

                # Parse the section
                # print "Consuming %s bytes (%s:%s) for %s"%(size, i+offset, i+offset+size, parser['dest'])
                value = struct.unpack(parser['pack'], ehdata[offset: offset+size])

                # Process the packed value
                value = parser['load'](value)

                # Update the slice
                for dest,v in zip(parser.get('dest', []), value):
                    sslice[dest] = v
                for dest,v in zip(parser.get('also', []), value):
                    sslice[dest] = v

                # Read the next section
                offset += size

            ed.append(sslice)

        return ed

    def _extheader_getkeys(self, flags):
        keys = []
        for i in sorted(self.extheader_flags.keys()):
            if flags & i:
                keys.append(i)
        return keys

@Handler.register('jadas')
class JADASHandler(FileHandler):
    pass
    # rectype = 'ccd_jadas'
    # 
    # def get_upload_items(self):
    #     # This is run for a .tif file produced by JADAS. Find the associated .xml files, load them, map as many
    #     # parameters as possible, and attach the raw xml file.
    #     jadas_params, foundfiles = self.load_jadas_xml()
    #     
    #     newrecord = {}
    #     newrecord["name"] = -100
    #     newrecord["rectype"] = "ccd_jadas"
    #     newrecord["id_micrograph"] = os.path.basename(self.filename)
    #     newrecord.update(self.applyparams)
    #     newrecord.update(jadas_params)
    #     newrecord["parents"] = [self.name]
    #     
    #     files = [emdash.transport.UploadTransport(name=-100, filename=self.filename, param='file_binary_image')]
    #     files[0].newrecord = newrecord
    #     
    #     for i in foundfiles:
    #         files.append(emdash.transport.UploadTransport(name=-100, filename=i, compress=False))
    #             
    #     return files
    # 
    # def load_jadas_xml(self):
    #     # find related XML files, according to JADAS naming conventions
    #     # take off the .tif, because the xml could be either file.tif_metadata.xml or file_metadata.xml
    #     if not ET:
    #         raise ImportError, "The ElementTree package (xml.etree.ElementTree) is required"
    #         
    #     foundfiles = []
    #     ret = {}        
    #     for xmlfile in glob.glob('%s_*.xml'%self.filename) + glob.glob('%s_*.xml'%self.filename.replace('.tif','')):
    #         print "Attempting to load ", xmlfile
    #         try:
    #             e = ET.parse(xmlfile)
    #             root = e.getroot()
    #             # There should be a loader for each root tag type, e.g. TemParameter -> map_jadas_TemParameter
    #             loader = getattr(self, 'map_jadas_%s'%root.tag, None)
    #             if loader:
    #                 ret.update(loader(root))
    #                 foundfiles.append(xmlfile)
    #         except Exception, e:
    #             print "Could not load %s: %s"%(xmlfile, e)
    # 
    #     return ret, foundfiles
    # 
    # def map_jadas_TemParameter(self, root):
    #     """One of these long, ugly, metadata-mapping methods"""
    #     ret = {}
    #     # Defocus
    #     ret['defocus_absdac'] = root.find('Defocus/defocus').get('absDac')
    #     ret['defocus_realphysval'] = root.find('Defocus/defocus').get('relPhisVal')
    #     ret['intendeddefocus_valinnm'] = root.find('Defocus/intendedDefocus').get('valInNm')
    #     d = root.find('Defocus/intendedDefocus').get('valInNm')
    #     if d != None:
    #         d = float(d) / 1000.0
    #         ret['ctf_defocus_set'] = d
    # 
    #     # Eos
    #     ret['eos_brightdarkmode'] = root.find('Eos/eos').get('brightDarkMode')
    #     ret['eos_darklevel'] = root.find('Eos/eos').get('darkLevel')
    #     ret['eos_stiglevel'] = root.find('Eos/eos').get('stigLevel')
    #     ret['eos_temasidmode'] = root.find('Eos/eos').get('temAsidMode')
    #     ret['eos_htlevel'] = root.find('Eos/eos').get('htLevel')
    #     ret['eos_imagingmode'] = root.find('Eos/eos').get('imagingMode')
    #     ret['eos_magcamindex'] = root.find('Eos/eos').get('magCamIndex')
    #     ret['eos_spectrummode'] = root.find('Eos/eos').get('spectrumMode')
    #     ret['eos_illuminationmode'] = root.find('Eos/eos').get('illuminationMode')
    #     ret['eos_spot'] = root.find('Eos/eos').get('spot')
    #     ret['eos_alpha'] = root.find('Eos/eos').get('alpha')
    # 
    #     # Lens
    #     ret['lens_cl1dac'] = root.find('Lens/lens').get('cl1Dac')
    #     ret['lens_cl2dac'] = root.find('Lens/lens').get('cl2Dac')
    #     ret['lens_cl3dac'] = root.find('Lens/lens').get('cl3Dac')
    #     ret['lens_cmdac'] = root.find('Lens/lens').get('cmDac')
    #     ret['lens_il1dac'] = root.find('Lens/lens').get('il1Dac')
    #     ret['lens_il2dac'] = root.find('Lens/lens').get('il2Dac')
    #     ret['lens_il3dac'] = root.find('Lens/lens').get('il3Dac')
    #     ret['lens_il4dac'] = root.find('Lens/lens').get('il4Dac')
    #     ret['lens_pl1dac'] = root.find('Lens/lens').get('pl1Dac')
    #     ret['lens_pl2dac'] = root.find('Lens/lens').get('pl2Dac')
    #     ret['lens_pl3dac'] = root.find('Lens/lens').get('pl3Dac')
    #     
    #     # Def
    #     ret['def_gunshiftx'] = root.find('Def/def').get('gunShiftX')
    #     ret['def_gunshifty'] = root.find('Def/def').get('gunShiftY')
    #     ret['def_guntiltx'] = root.find('Def/def').get('gunTiltX')
    #     ret['def_guntilty'] = root.find('Def/def').get('gunTiltY')
    #     ret['def_beamshiftx'] = root.find('Def/def').get('beamShiftX')
    #     ret['def_beamshifty'] = root.find('Def/def').get('beamShiftY')
    #     ret['def_beamtiltx'] = root.find('Def/def').get('beamTiltX')
    #     ret['def_beamtilty'] = root.find('Def/def').get('beamTiltY')            
    #     ret['def_clstigx'] = root.find('Def/def').get('clStigX')
    #     ret['def_clstigy'] = root.find('Def/def').get('clStigY')
    #     ret['def_olstigx'] = root.find('Def/def').get('olStigX')
    #     ret['def_olstigy'] = root.find('Def/def').get('olStigY')
    #     ret['def_ilstigx'] = root.find('Def/def').get('ilStigX')
    #     ret['def_ilstigy'] = root.find('Def/def').get('ilStigY')
    #     ret['def_imageshiftx'] = root.find('Def/def').get('imageShiftX')
    #     ret['def_imageshifty'] = root.find('Def/def').get('imageShiftY')
    #     ret['def_plax'] = root.find('Def/def').get('plaX')
    #     ret['def_play'] = root.find('Def/def').get('plaY')
    #     
    #     # HT
    #     ret['ht_ht'] = root.find('HT/ht').get('ht')
    #     ret['ht_energyshift'] = root.find('HT/ht').get('energyShift')
    #     
    #     # MDS
    #     ret['mds_mdsmode'] = root.find('MDS/mds').get('mdsMode')
    #     ret['mds_blankingdef'] = root.find('MDS/mds').get('blankingDef')
    #     ret['mds_defx'] = root.find('MDS/mds').get('defX')
    #     ret['mds_defy'] = root.find('MDS/mds').get('defY')
    #     ret['mds_blankingtype'] = root.find('MDS/mds').get('blankingType')
    #     ret['mds_blankingtime'] = root.find('MDS/mds').get('blankingTime')
    #     ret['mds_shutterdelay'] = root.find('MDS/mds').get('shutterDelay')
    #     
    #     # Photo
    #     ret['photo_exposuremode'] = root.find('PHOTO/photo').get('exposureMode')
    #     ret['photo_manualexptime'] = root.find('PHOTO/photo').get('manualExpTime')
    #     ret['photo_filmtext'] = root.find('PHOTO/photo').get('filmText')
    #     ret['photo_filmnumber'] = root.find('PHOTO/photo').get('filmNumber')
    #     
    #     # GonioPos
    #     ret['goniopos_x'] = root.find('GonioPos/gonioPos').get('x')
    #     ret['goniopos_y'] = root.find('GonioPos/gonioPos').get('y')
    #     ret['goniopos_z'] = root.find('GonioPos/gonioPos').get('z')
    #     ret['goniopos_tiltx'] = root.find('GonioPos/gonioPos').get('tiltX')
    #     ret['goniopos_rotortilty'] = root.find('GonioPos/gonioPos').get('rotOrTiltY')
    # 
    #     return ret
    #     
    # def map_jadas_DigitalCameraParameter(self, root):
    #     attrmap = {
    #         'CameraName': 'ccd_id',
    #         'AreaTop': 'digicamprm_areatop',
    #         'AreaBottom': 'digicamprm_areabottom',
    #         'AreaLeft': 'digicamprm_arealeft',
    #         'AreaRight': 'digicamprm_arearight',
    #         'Exposure': 'time_exposure_tem',
    #         'Binning': 'binning',
    #         'PreIrradiation': 'digicamcond_preirradiation',
    #         'BlankingTime': 'digicamcond_blankingtime',
    #         'BlankBeam': 'digicamcond_blankbeam',
    #         'CloseScreen': 'digicamcond_closescreen',
    #         'DataFormat': 'digicamcond_dataformat'        
    #     }
    # 
    #     ret = {}
    #     for i in root.findall('*/tagCamPrm'):
    #         param = attrmap.get(i.get('tagAttrName'))
    #         value = i.get('tagAttrVal')
    #         if param != None and value != None:
    #             ret[param] = value        
    # 
    #     return ret
    #     
    # def map_jadas_IntensityBasedHoleSelection(self, root):
    #     ret = {}
    #     return ret

