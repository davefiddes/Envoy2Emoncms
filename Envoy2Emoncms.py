#!/usr/bin/python3

# This utility sends envoy (enphase) data to emoncms
#
# coded by:
# author : Edwin Bontenbal
# Email : Edwin.Bontenbal@Gmail.COM
import time
import json
import logging
import logging.config
import configparser
import requests

Version = "v1.00"


# If you experience errors while executing this script, make sure you installed
# python and the required modules/libraries

TimeStampList = {}
DataJson_inv = {}
DataJson_sum = {}

TranslationList = {}

# Allow programming logging to be configured externally
logging.config.fileConfig("/etc/Envoy2Emoncms/logging.conf")

###############################################################################
# Procedures
###############################################################################

Config = configparser.ConfigParser()
Config.read("/etc/Envoy2Emoncms/Envoy2Emoncms.cfg")


def ConfigSectionMap(section):
    dict1 = {}
    options = Config.options(section)
    for option in options:
        try:
            dict1[option] = Config.get(section, option)
            logging.debug("Reading config file : " + section +
                          "," + option + " = " + dict1[option])
            if dict1[option] == -1:
                print("skip: %s" % option)
        except:
            print(f"exception on {option}!")
            dict1[option] = None
    return dict1


print(Config.sections())

emon_privateKey = ConfigSectionMap("emoncms")['privatekey']
emon_node_panel = ConfigSectionMap("emoncms")['node_panel']
emon_node_sum = ConfigSectionMap("emoncms")['node_sum']
emon_host = ConfigSectionMap("emoncms")['host']
emon_protocol = ConfigSectionMap("emoncms")['protocol']
emon_url = ConfigSectionMap("emoncms")['url']

envoy_url_inv = ConfigSectionMap("envoy")['url_inv']
envoy_url_sum = ConfigSectionMap("envoy")['url_sum']
envoy_host = ConfigSectionMap("envoy")['host']
envoy_protocol = ConfigSectionMap("envoy")['protocol']
envoy_realm = ConfigSectionMap("envoy")['realm']
envoy_username = ConfigSectionMap("envoy")['username']
envoy_password = ConfigSectionMap("envoy")['password']

options = Config.options('translationlist')
for option in options:
    try:
        TranslationList[option] = Config.get('translationlist', option)
        logging.debug("Reading config file : translationlist," +
                      option + " = " + TranslationList[option])
    except:
        print(f"exception on {option}!")

###############################################################################
# Main program
###############################################################################

# Construct urls
url_envoy_inv = envoy_protocol + envoy_host + envoy_url_inv
url_envoy_sum = envoy_protocol + envoy_host + envoy_url_sum
emoncms_post_url = emon_protocol + emon_host + emon_url

envoy_session = requests.Session()
envoy_session.auth = requests.auth.HTTPDigestAuth(
    envoy_username, envoy_password)

emoncms_session = requests.Session()

logging.info("Envoy2Emoncms %s starting", Version)

# Do forever ....

while True:
    # Fetch page with ENVOY inverter data
    page_content_inv = envoy_session.get(url_envoy_inv)
    the_page_inv = page_content_inv.text
    logging.debug(the_page_inv)
    data_inv = page_content_inv.json()

    # Fetch page with ENVOY general data
    page_content_sum = envoy_session.get(url_envoy_sum)
    the_page_sum = page_content_sum.text
    logging.debug(the_page_sum)
    data_sum = page_content_sum.json()

    DataJson_inv.clear()
    DataJson_sum.clear()

    # Determine panel and array according to translation list, based on naming
    for inverter in data_inv:
        serial_number = inverter['serialNumber']
        last_report_time = inverter['lastReportDate']
        last_report_watts = inverter['lastReportWatts']
        max_report_watts = inverter['maxReportWatts']

        if serial_number in TranslationList:
            # Serial in list use alias
            PanelID = TranslationList[serial_number]
            logging.debug("Inverter found in list : %s -> %s",
                          serial_number, PanelID)
        else:
            # Serial not in list use serial
            PanelID = serial_number
            logging.debug("Inverter not found in list : %s", serial_number)

        logging.debug("Serial          : %s", serial_number)
        logging.debug("LastReportDate  : %s", last_report_time)
        logging.debug("lastReportWatts : %s", last_report_watts)
        if serial_number not in TimeStampList:
            # Ensure we always have an entry in the TimeStampList
            TimeStampList[serial_number] = 0
            logging.debug("Initial report for : %s", serial_number)

        if last_report_time > TimeStampList[serial_number]:
            logging.debug("Update, newer timestamp found")
            logging.debug(
                "Update timestamp : %s Previous timestamp : %s",
                last_report_time,
                TimeStampList[serial_number])

            DataJson_inv[PanelID + '_LRW'] = last_report_watts
            DataJson_inv[PanelID + '_MRW'] = max_report_watts
            DataJson_inv[PanelID + '_IVO'] = 1
            TimeStampList[serial_number] = last_report_time

    if DataJson_inv:
        logging.debug("New inverter data found, so push to emoncms")
        inverter_payload = {
            "node": emon_node_panel,
            "apikey": emon_privateKey,
            "fulljson": json.dumps(DataJson_inv, separators=(',', ':'))
        }
        logging.debug(inverter_payload)
        HTTPresult_inv = emoncms_session.post(
            emoncms_post_url, data=inverter_payload)
        logging.debug("Response code : %s", HTTPresult_inv.status_code)
    else:
        logging.debug(
            "No new inverter data found, so nothing to push to emoncms")

    DataJson_sum['wattHoursToday'] = data_sum['wattHoursToday']
    DataJson_sum['wattHoursLifetime'] = data_sum['wattHoursLifetime']
    DataJson_sum['wattsNow'] = data_sum['wattsNow']

    summary_payload = {
        "node": emon_node_sum,
        "apikey": emon_privateKey,
        "fulljson": json.dumps(DataJson_sum, separators=(',', ':'))
    }
    logging.debug(summary_payload)
    HTTPresult_sum = emoncms_session.post(
        emoncms_post_url, data=summary_payload)
    logging.debug("Response code : %s", HTTPresult_sum.status_code)

    time.sleep(15)
