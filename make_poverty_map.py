from pykml.factory import KML_ElementMaker as KML
from pykml import parser

from lxml import etree

import matplotlib.pyplot as plt
from colormap.colors import rgb2hex

import json
import math

import urllib
import xml.dom.minidom
import json

try:
    import google_key
except:
    print('!' * 30)
    print('!' * 30)
    print(
        'You need to add a Google Maps Key! Make one here' +
        ': https://code.google.com/apis/console/'
    )
    print(
        'Then make a file called google_key.py and add a line like this:'
    )
    print(
        'mapsKey = XXXXXXXXXXXXXXXXXX'
    )
    print('!' * 30)
    print('!' * 30)
    exit()

import pandas as pd

##############################################################################
##############################################################################
#######    Funtion to convert string address to coordinate.         ##########
##############################################################################
##############################################################################
def geocode(address, sensor=False):
    # This function queries the Google Maps API geocoder with an
    # address. It gets back a csv file, which it then parses and
    # returns a string with the longitude and latitude of the address.

    # This isn't an actual maps key, you'll have to get one yourself.
    # Sign up for one here: https://code.google.com/apis/console/
    mapsKey = google_key.mapsKey
    mapsUrl = 'https://maps.googleapis.com/maps/api/geocode/json?address='

    # This joins the parts of the URL together into one string.
    url = ''.join([mapsUrl,urllib.request.quote(address),'&sensor=',str(sensor).lower(), '&key=',mapsKey])
    jsonOutput = str(urllib.request.urlopen(url).read ()) # get the response
    # fix the output so that the json.loads function will handle it correctly
    jsonOutput=jsonOutput.replace ("\\n", "")
    try:
        result = json.loads(jsonOutput[2:-1]) # converts jsonOutput into a dictionary
    except:
        print(address)
        return None
    # check status is ok i.e. we have results (don't want to get exceptions)
    if result['status'] != "OK":
        return ""
    coordinates=result['results'][0]['geometry']['location'] # extract the geometry
    return coordinates['lng'], coordinates['lat']

##############################################################################
##############################################################################
#######                           Load data.                        ##########
##############################################################################
##############################################################################

print('Loading CCSCC location data from file...')

# Zip codes in Santa Clara County.
santa_clara_zip_codes = [int(a) for a in open('zip_codes.txt').read().split()]

# List of locations from CCSCC.
location_data = pd.read_csv('locations.csv', encoding = "ISO-8859-1")

# Create mapping from zip code to demographic data.
data = {}
for zip_code in santa_clara_zip_codes:
    data[zip_code] = {'households': 0, 'poverty_rate': 0}

# Load number of households in each zip code from file.
with open('households.json') as f:
    lines = json.load(f)
    for line in lines:
        zip = int(line[1])
        if zip in santa_clara_zip_codes:
            households = int(line[0])
            data[zip]['households'] = households

# Load poverty rate data in each zip code from file.
max_poverty_rate = 0
with open('poverty_rate.json') as f:
    lines = json.load(f)
    for line in lines:
        zip = int(line[1])
        if zip in santa_clara_zip_codes:
            poverty_rate = float(line[0])
            data[zip]['poverty_rate'] = poverty_rate
            if poverty_rate > max_poverty_rate:
                max_poverty_rate = poverty_rate

# Load zip code coordinates from file.
print('Loading zip code data from file...')
path = 'cb_2019_us_zcta510_500k.kml' 
with open(path) as f:
    try:
        root = parser.parse(f)
    except:
        print('!' * 30)
        print('!' * 30)
        print('Zip code map data not yet downloaded!')
        print('You need to run "git lfs pull"')
        print('To install git lfs, go here: https://git-lfs.github.com/')
        print('!' * 30)
        print('!' * 30)
        exit()

areas = {}

print('Removing zip codes not in Santa Clara from map...')

for placemark in root.getroot().Document.Folder.Placemark:
    zip_code = placemark.ExtendedData.SchemaData.SimpleData
    if zip_code not in santa_clara_zip_codes:
        parent = placemark.getparent()
        parent.remove(placemark)
    else:
        placemark.description = '# of Households: %d, Poverty Rate: %.2f%%' % (
            data[zip_code]['households'], data[zip_code]['poverty_rate']
        )
        placemark.remove(placemark.styleUrl)
        placemark.remove(placemark.ExtendedData)
        placemark.append(etree.fromstring("""
            <Style id="%dstyle">
                <PolyStyle>
                    <color>%s</color>
                </PolyStyle>
            </Style>
        """ % (
            zip_code,
            '#' + hex(int(255 * data[zip_code]['poverty_rate'] / max_poverty_rate))[2:] + 'FF0000'
        )))

##############################################################################
##############################################################################
#######              Add styles for each type of marker.            ##########
##############################################################################
##############################################################################

def pin_style_xml(type, url):
    return """
        <Style id="%s">
            <IconStyle>
                <Icon>
                    <href>%s</href>
                    <scale>1.0</scale>
                </Icon>
            </IconStyle>
        </Style>
    """ % (type, url)

pin_styles = [
    pin_style_xml('hq', 'https://img.icons8.com/fluent/48/000000/cottage.png'),
    pin_style_xml('adult_day_care', 'https://img.icons8.com/fluent/48/000000/marker-sun.png'),
    pin_style_xml('family_resource_center', 'https://img.icons8.com/bubbles/50/000000/family.png'),
    pin_style_xml('senior_program', 'https://img.icons8.com/ios/50/000000/elderly-person.png'),
    pin_style_xml('youth_center', 'https://img.icons8.com/cotton/64/000000/christmas-kid-2.png'),
    pin_style_xml('parish', 'https://dsjdev.wpengine.com/kml/parish_icon.png'),
    pin_style_xml('essential', 'https://img.icons8.com/dusk/64/000000/high-importance.png')
]

type_map = {
    'HQ': 'hq',
    'Adult Day Care': 'adult_day_care',
    'Family Resource Center': 'family_resource_center',
    'Senior Program': 'senior_program',
    'Youth Center': 'youth_center',
    'Parish': 'parish',
    'Essential': 'essential'
}


for pin_style in pin_styles:
    root.getroot().Document.append(etree.fromstring(pin_style))

print('Adding placemarks for CCSCC locations...')

for index, row in location_data.iterrows():
    if not isinstance(row['Address'], float) or not math.isnan(row['Address']):
        coord = geocode(row['Address'])
        if coord:
            root.getroot().Document.Folder.append(etree.fromstring("""
                <Placemark id="mountainpin1">
                    <name>%s: %s</name>
                    <styleUrl>#%s</styleUrl>
                    <Point>
                        <coordinates>%f, %f ,0</coordinates>
                    </Point>
                </Placemark>
            """ % (row['Type'], row['Name'], type_map[row['Type']], coord[0], coord[1])))

print('Map creation complete.')
print('Writing poverty map to file: poverty_map.kml')
with open('poverty_map.kml', 'wb') as f:
    f.write(etree.tostring(root, pretty_print=True))
