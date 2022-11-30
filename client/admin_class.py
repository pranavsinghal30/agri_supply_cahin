#!/bin/python3
from client import *

class admin():
    def __init__(self):
        pass

    def addManufacturer(self, manufacturerName):
        logging.info('addManufacturer({})'.format(manufacturerName))
        input_address_list = [MANUFACTURERS_TABLE]
        output_address_list = [MANUFACTURERS_TABLE,
                               getManufacturerAddress(manufacturerName)]
        response = wrap_and_send(
            "addManufacturer", manufacturerName, input_address_list, output_address_list, wait=5)
        # print ("manufacture response: {}".format(response))
        return yaml.safe_load(response)['data'][0]['status']

    def addDistributer(self, distributerName):
        logging.info('addDistributer({})'.format(distributerName))
        distHasAddress = getDistributerAddress(distributerName, "has")
        distReqAddress = getDistributerAddress(distributerName, "request")
        input_address_list = [DISTRIBUTERS_TABLE]
        output_address_list = [DISTRIBUTERS_TABLE,
                               distHasAddress, distReqAddress]
        response = wrap_and_send(
            "addDistributor", distributerName, input_address_list, output_address_list, wait=5)
        print ("manufacture response: {}".format(response))
        return yaml.safe_load(response)['data'][0]['status']

    def addPharmacy(self, PharmacyName):
        logging.info('addPharmacy({})'.format(PharmacyName))
        PharmacyReqAddress = getPharmacyAddress(PharmacyName, "request")
        PharmacyHasAddress = getPharmacyAddress(PharmacyName, "has")
        input_address_list = [PHARMACY_TABLE]
        output_address_list = [PHARMACY_TABLE,
                               PharmacyHasAddress, PharmacyReqAddress]
        response = wrap_and_send(
            "addPharmacy", PharmacyName, input_address_list, output_address_list, wait=5)
        # print ("manufacture response: {}".format(response))
        return yaml.safe_load(response)['data'][0]['status']

    def listClients(self, clientAddress):
        result = send_to_rest_api("state/{}".format(clientAddress))
        try:
            return (base64.b64decode(yaml.safe_load(result)["data"])).decode()
        except BaseException:
            return None

    def listPharmacies(self):
        return listClients(PHARMACY_TABLE)

    def listDistributers(self):
        return listClients(DISTRIBUTERS_TABLE)

    def listManufacturers(self):
        return listClients(MANUFACTURERS_TABLE)        
    
