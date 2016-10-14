# the test file
# FireLoc375_npp_d20161014_t1053316_e1104545_b00001_c20161014130840100000_ipop_dev.txt 
# FireLoc375_???_d????????_t???????_e???????_b?????_c????????????????????_ipop_dev.txt 
# is derived from the VF375 product and an indicator that that file is complete

import sys
import datetime
import glob
import os

pathL1 = "v:\\"
pathL2 = "w:\\"
logDir = "C:\\fiddle\\VIIRS\\logs"
daysLog = "viirs_days.txt"
filesLog = "viirs_files.txt"
prefixL1 = ["SVM07",
            "SVM08",
            "SVM10",
            "SVM11",
            "GITCO",
            "GMTCO"]
              
prefixL2 = ["AVAFO",
            "VF375"]

# Check for new day's folder
#beforeDayFolder = dict ([(f, None) for f in os.listdir (pathL2)])
#while 1: 
#    time.sleep (60*60)
#    afterDayFolder = dict ([(f, None) for f in os.listdir (path_to_watch)])
#    addedDayFolder = [f for f in after if not f in before]
#    removedDayFolder = [f for f in before if not f in after]
#    if addedDayFolder: print "Added: ", ", ".join (added)
#    if removedDayFolder: print "Removed: ", ", ".join (removed)
#    beforeDayFolder = afterDayFolder
    
def readDaysLog():
    with open(os.path.join(logDir, daysLog)) as log:
        return [line.strip() for line in log]
    
def appendLog(list, log):
    with open(log, 'a') as l:
        for i in list:
            l.write(i + "\n")
    
    
# Get list of days 
days = glob.glob(os.path.join(pathL2,'[0-9][0-9][0-9][0-9][0-9][0-9][0-9]'))
pastDays = readDaysLog()
newDays = [d for d in days if not d in pastDays]
#print pastDays
print days == pastDays
print newDays

acquisitions = []
for d in newDays:
    acquisitions.append(glob.glob(os.path.join(d, 'FireLoc375_???_d????????_t???????_e???????_b?????_c????????????????????_ipop_dev.txt')))
print acquisitions

              
              
              
              
              
              
              
              