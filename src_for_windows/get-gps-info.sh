#!/bin/bash

#write gps position into filename.txt
#get-gps-info.sh

#j=0
#for image in *.JPG ; do
#    echo $image
#    filename="${image%.*}"
#    exiftool $image | grep -i "GPS"> $filename.txt
#done

#------------------------------------------------------------------------------
# File:         gpx.fmt
#
# Description:  Example ExifTool print format file for generating GPX track log
#
# Usage:        exiftool -p gpx.fmt -d %Y-%m-%dT%H:%M:%SZ FILE [...] > out.gpx
#
# Requires:     ExifTool version 8.10 or later
#
# Revisions:    2010/02/05 - P. Harvey created
#
# Notes:     1) All input files must contain GPSLatitude and GPSLongitude.
#            2) The -fileOrder option may be used to control the order of the
#               generated track points.
#------------------------------------------------------------------------------
if [ -d "$1" ]; then
    echo "#[HEAD]<?xml version=\"1.0\" encoding=\"utf-8\"?>" > $1/gpx.fmt
    echo "#[HEAD]<gpx version=\"1.0\"" >> $1/gpx.fmt
    echo "#[HEAD] creator=\"ExifTool $ExifToolVersion\"" >> $1/gpx.fmt
    echo "#[HEAD] xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"" >> $1/gpx.fmt
    echo "#[HEAD] xmlns=\"http://www.topografix.com/GPX/1/0\"" >> $1/gpx.fmt
    echo "#[HEAD] xsi:schemaLocation=\"http://www.topografix.com/GPX/1/0 http://www.topografix.com/GPX/1/0/gpx.xsd\">" >> $1/gpx.fmt
    echo "#[HEAD]<trk>" >> $1/gpx.fmt
    echo "#[HEAD]<number>1</number>" >> $1/gpx.fmt
    echo "#[HEAD]<trkseg>" >> $1/gpx.fmt
    echo "#[BODY]<trkpt lat=\"\$gpslatitude#\" lon=\"\$gpslongitude#\">" >> $1/gpx.fmt
    echo "#[BODY]  <ele>\$gpsaltitude#</ele>" >> $1/gpx.fmt
    echo "#[BODY]  <time>\$datetimeoriginal</time>" >> $1/gpx.fmt
    echo "#[BODY]  <name>\$filename</name>" >> $1/gpx.fmt
    echo "#[BODY]  <link href=\"\$directory/\$filename\"/>" >> $1/gpx.fmt
    echo "#[BODY]</trkpt>" >> $1/gpx.fmt
    echo "#[TAIL]</trkseg>" >> $1/gpx.fmt
    echo "#[TAIL]</trk>" >> $1/gpx.fmt
    echo "#[TAIL]</gpx>" >> $1/gpx.fmt

    exiftool -r -q -q -if '$gpsaltitude' -fileOrder datetimeorginal -p $1/gpx.fmt -d %Y-%m-%dT%H:%M:%SZ $1 > $1/out.gpx
    rm $1/gpx.fmt
fi
#roslaunch imgdir2rosmsg img2ros.launch &

#gpsprune out.gpx &
