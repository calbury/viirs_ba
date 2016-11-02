import sys
import os
import psycopg2
import time
import datetime
import collections
import glob

def get_time():
    ts = time.time()
    dt = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    return dt
    
def execute_read_query(queryText):
    print "Start", queryText, get_time()
    ConnParam = "dbname={0} user={1} password={2}".format(DBname, DBuser, pwd)
    conn = psycopg2.connect(ConnParam)
    # Open a cursor to perform database operations
    cur = conn.cursor()
    cur.execute(queryText)
    rows = cur.fetchall()
    conn.commit()
    # Close communication with the database
    cur.close()
    conn.close()
    print "End", queryText, get_time()
    return rows


    
################################################################################
scriptsDir =  r"C:\fiddle\VIIRS\viirs_ba\scripts"
outputDir = r"C:\fiddle\VIIRS\Outputs"
iniFile = "operatinalVIIRS.ini"   
DBname = "VIIRS_burned_area"
DBuser = "postgres"
pwd = "sokkia"
pathL1 = "v:\\"
pathL2 = "w:\\"
#d = 'd20160925_t1955425'
schema = "operational"
runningFlagFile = r"C:\fiddle\VIIRS\viirs_ba\scripts\viirsIsRunning.txt"

# check to see if VIIRS_threshold_reflCor_Bulk is already running
if os.path.exists(r"C:\fiddle\VIIRS\viirs_ba\scripts\viirsIsRunning.txt"):
    print "This process is already running."
    sys.exit()


processedScenesQuery = "SELECT year_jday, time_stamp FROM {0}.processed_scenes".format(schema)
try:
    scene_list = execute_read_query(processedScenesQuery)
    sd = collections.defaultdict(list)
    pastDays = []
    for i in scene_list:
        sd[i[0]].append(i[1].strip())
    for key, value in sd.iteritems():
        pastDays.append(str(key))
except:
    sd = collections.defaultdict(list)
    pastDays = []
#for k, v in sd.iteritems():
#    print k
#    print v
    
# Get list of days 
days = glob.glob(os.path.join(pathL1,'[0-9][0-9][0-9][0-9][0-9][0-9][0-9]'))
days = [d.replace(pathL1,'') for d in days]
#newDays = [d for d in days if d not in pastDays]
newDays = days
acquisitions = []
for d in newDays:
    for i in glob.glob(os.path.join(pathL2, d, 'FireLoc375_???_d????????_t???????_e???????_b?????_c????????????????????_ipop_dev.txt')):
        acquisitions.append(i)

timeStamps = []         
for i in acquisitions:
    jday = i.split("\\")[1]
    ts = i.split("\\")[2][15:33]
    #print ts
    #print jday
    #print sd[jday]
    if ts not in sd[int(jday)]:
        timeStamps.append(ts)
#for i in timeStamps:
#    print i
setTimeStamps = set(timeStamps)

print len(timeStamps)
print len(setTimeStamps)

iniText = """
[InDirectory]
L1BaseDirectory = {0}   ; Directory containing level 1 VIIRS imagery
L2BaseDirectory = {1}   ; Directory containing level 2 VIIRS imagery

[Burnmask]
schema = landmask
table  = noburn

[ActiveFire] 
use375af = y          ; Flag to use I-band 375 m active fire data, VF375 (y or n)
use750af = y          ; Flag to use M-band 750 m active fire data, AVAFO (y or n)
limit375 = 10         ; Limits the number of high conf 375 fires in one row

[Thresholds]
M07UB = 0.19        ; Band 07 (0.86 um)upper bound this value has been updated to VIIRS calibration
M08LB = 0.00        ; Band 08 (1.24 um)lower bound this value has been updated to VIIRS calibration
M08UB = 0.28        ; Band 08 (1.24 um)upper bound this value has been updated to VIIRS calibration
M10LB = 0.7         ; Band 10 (1.61 um)lower bound this value has been updated to VIIRS calibration
M10UB = 1.0         ; Band 10 (1.61 um)upper bound this value has been updated to VIIRS calibration
M11LB = 0.05        ; Band 11 (2.25 um)lower bound this value has been updated to VIIRS calibration
RthSub = 0.05       ; RthSub is the factor subtracted from the 1.240 band when comparing to the Rth
Rth = 0.81          ; Rth
RthLB =  0.0        ; RthLB is the factor that the Rth check must be greater than or equal to 
MaxSolZen = 96      ; Maximum solar zenith angle, used to filter out night pixels from burned area thresholding 

[ConfirmBurnParameters]
TemporalProximity = 10 ; Time window for a burned area to be within (days)
SpatialProximity = 5000	   ; Distance (meters) from a active fire point for a burned area to be considered valid

[OutputFlags]
TextFile = y        ; Flag to trigger text file output (y or n) 
PostGIS = y         ; Flag to trigger push to PostGis (y or n)
Shapefile = y
OutShapeDir  = {2}  ; This folder is used for all non-db outputs.

PostgresqlBin = C:\\Program Files\\PostgreSQL\\9.5\\bin     ; Path to directory with postgresql binaries (including pgsql2shp).

[DataBaseInfo]
DataBaseName = VIIRS_burned_area    ; Name of database
Schema   = {3}                 ; Name of schema
UserName = postgres                 ; Database User Name
password = sokkia                   ; Database Password

[GeogWindow]
North = 50
South = 30.8
East  = -101
West  = -126

[ImageDates]
ImageDates = """
#print iniText.format(d for d in newDays)
if os.path.exists(os.path.join(scriptsDir, iniFile)):
    os.remove(os.path.join(scriptsDir, iniFile))
with open(os.path.join(scriptsDir, iniFile), "w") as ini:
    ini.write(iniText.format(pathL1, pathL2, outputDir, schema))
with open(os.path.join(scriptsDir, iniFile), "a") as ini: 
   #ini.write(''.join('{},'.format(d) for d in timeStamps))
   ini.write(','.join(d for d in timeStamps))
   #ini.write(','.join(timeStamps()))

if len(timeStamps) > 0:   
    sysCommand = r"C:\fiddle\VIIRS\viirs_ba\scripts\VIIRS_threshold_reflCor_Bulk.py " + r"C:\fiddle\VIIRS\viirs_ba\scripts\operatinalVIIRS.ini" 
    print len(timeStamps), "new images. Kicking off process."
    print sysCommand
    os.system(sysCommand)
else:
    print "No new images, doing nothing."

# Remove the running flag file
if os.path.exists(runningFlagFile):
    os.remove(runningFlagFile)