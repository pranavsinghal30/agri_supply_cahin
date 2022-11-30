#!/usr/bin/python3
import hashlib
import base64
import random
import time
import requests
import yaml
import sys
import logging
import optparse
from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory
from sawtooth_signing import ParseError
from sawtooth_signing.secp256k1 import Secp256k1PrivateKey
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_sdk.protobuf.transaction_pb2 import Transaction
from sawtooth_sdk.protobuf.batch_pb2 import BatchList
from sawtooth_sdk.protobuf.batch_pb2 import BatchHeader
from sawtooth_sdk.protobuf.batch_pb2 import Batch

logging.basicConfig(filename='client.log',level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

parser = optparse.OptionParser()
parser.add_option('-U', '--url', action = "store", dest = "url", default = "http://rest-api:8008")

def hash(data):
    return hashlib.sha512(data.encode()).hexdigest()

family_name = "pharma"
FAMILY_NAME = hash(family_name)[:6]

TABLES = hash("tables")[:6]

TRACKING = hash("tracking")[:6]
TRACKING_TABLE = FAMILY_NAME + TRACKING

MANUFACTURER_ENTRIES = hash("manufacturer-entries")[:6]
MANUFACTURERS = hash("manufacturers")
MANUFACTURERS_TABLE = FAMILY_NAME + TABLES + MANUFACTURERS[:58]

DISTRIBUTER_ENTRIES = hash("distributer-entries")[:6]
DISTRIBUTERS = hash("distributers")
DISTRIBUTERS_TABLE = FAMILY_NAME + TABLES + DISTRIBUTERS[:58]

PHARMACY_ENTRIES = hash("pharmacy-entries")[:6]
PHARMACY = hash("pharmacys")
PHARMACY_TABLE = FAMILY_NAME + TABLES + PHARMACY[:58]

# random private key
context = create_context('secp256k1')
private_key = context.new_random_private_key()
signer = CryptoFactory(context).new_signer(private_key)
public_key = signer.get_public_key().as_hex()

base_url = 'http://rest-api:8008'

def getBatchAddress(batchID):
    return TRACKING_TABLE + hash(batchID)[:58]

def getManufacturerAddress(manufacturerName):
    return FAMILY_NAME + MANUFACTURER_ENTRIES + hash(manufacturerName)[:58]

def getDistributerAddress(distributerName, qualifier = "has"):
    distributerName = str(distributerName)
    return FAMILY_NAME + DISTRIBUTER_ENTRIES + hash(distributerName)[:57] + hash(qualifier)[0]

def getPharmacyAddress(pharmacyname, qualifier = "has"):
    return FAMILY_NAME + PHARMACY_ENTRIES + hash(pharmacyname)[:57] + hash(qualifier)[0]

def addManufacturer(manufacturerName):
    logging.info ('addManufacturer({})'.format(manufacturerName))
    input_address_list = [MANUFACTURERS_TABLE]
    output_address_list = [MANUFACTURERS_TABLE, getManufacturerAddress(manufacturerName)]
    response = wrap_and_send("addManufacturer", manufacturerName, input_address_list, output_address_list, wait = 5)
    # print ("manufacture response: {}".format(response))
    return yaml.safe_load(response)['data'][0]['status']

def addPharmacy(pharmacy):
    logging.info ('addPharmacy({})'.format(pharmacy))
    input_address_list = [PHARMACY_TABLE]
    output_address_list = [PHARMACY_TABLE, getPharmacyAddress(pharmacy)]
    response = wrap_and_send("addPharmacy", pharmacy, input_address_list, output_address_list, wait = 5)
    # print ("manufacture response: {}".format(response))
    return yaml.safe_load(response)['data'][0]['status']

def addDistributer(distributerName):
    logging.info ('addDistributer({})'.format(distributerName))
    input_address_list = [DISTRIBUTERS_TABLE]
    output_address_list = [DISTRIBUTERS_TABLE, getDistributerAddress(distributerName)]
    response = wrap_and_send("addDistributor", distributerName, input_address_list, output_address_list, wait = 5)
    # print ("manufacture response: {}".format(response))
    return yaml.safe_load(response)['data'][0]['status']

def manufacture(manufacturerName, medicineName):
    logging.info ('manufacture({})'.format(medicineName))
    l = [manufacturerName, medicineName]
    manufacturerAddress = getManufacturerAddress(manufacturerName)
    command_string = ','.join(l)
    input_address_list = [MANUFACTURERS_TABLE, manufacturerAddress]
    output_address_list = [manufacturerAddress]
    response = wrap_and_send("manufacture", command_string, input_address_list, output_address_list, wait = 5)
    # print ("manufacture response: {}".format(response))
    return yaml.safe_load(response)['data'][0]['status']

def giveToDistributor(manufacturerName, distributer, medicineName):
    l = [manufacturerName, distributer, medicineName]
    command_string = ','.join(l)
    distributerAddress = getDistributerAddress(distributer)
    manufacturerAddress = getManufacturerAddress(manufacturerName)
    input_address_list = [DISTRIBUTERS_TABLE, MANUFACTURERS_TABLE, manufacturerAddress, distributerAddress]
    output_address_list = [manufacturerAddress, distributerAddress]
    response = wrap_and_send("giveTo", command_string, input_address_list, output_address_list, wait = 5)
    # print ("give response: {}".format(response))
    return yaml.safe_load(response)['data'][0]['status']

def listClients(clientAddress):
    result = send_to_rest_api("state/{}".format(clientAddress))
    try:
        return (base64.b64decode(yaml.safe_load(result)["data"])).decode()
    except BaseException:
        return None

def send_to_rest_api(suffix, data=None, content_type=None):
    url = "{}/{}".format(base_url, suffix)
    headers = {}
    logging.info ('sending to ' + url)
    if content_type is not None:
        headers['Content-Type'] = content_type
    try:
        if data is not None:
            result = requests.post(url, headers=headers, data=data)
            logging.info ("\nrequest sent POST\n")
        else:
            result = requests.get(url, headers=headers)
        if not result.ok:
            logging.debug ("Error {}: {}".format(result.status_code, result.reason))
            raise Exception("Error {}: {}".format(result.status_code, result.reason))
    except requests.ConnectionError as err:
        logging.debug ('Failed to connect to {}: {}'.format(url, str(err)))
        raise Exception('Failed to connect to {}: {}'.format(url, str(err)))
    except BaseException as err:
        raise Exception(err)
    return result.text

def wait_for_status(batch_id, result, wait = 10):
    '''Wait until transaction status is not PENDING (COMMITTED or error).
        'wait' is time to wait for status, in seconds.
    '''
    if wait and wait > 0:
        waited = 0
        start_time = time.time()
        logging.info ('url : ' + base_url + "batch_statuses?id={}&wait={}".format(batch_id, wait))
        while waited < wait:
            result = send_to_rest_api("batch_statuses?id={}&wait={}".format(batch_id, wait))
            status = yaml.safe_load(result)['data'][0]['status']
            waited = time.time() - start_time

            if status != 'PENDING':
                return result
        logging.debug ("Transaction timed out after waiting {} seconds.".format(wait))
        return "Transaction timed out after waiting {} seconds.".format(wait)
    else:
        return result


def wrap_and_send(action, data, input_address_list, output_address_list, wait=None):
    '''Create a transaction, then wrap it in a batch.
    '''
    payload = ",".join([action, str(data)])
    logging.info ('payload: {}'.format(payload))

    # Construct the address where we'll store our state.
    # Create a TransactionHeader.
    header = TransactionHeader(
        signer_public_key = public_key,
        family_name = family_name,
        family_version = "1.0",
        inputs = input_address_list,         # input_and_output_address_list,
        outputs = output_address_list,       # input_and_output_address_list,
        dependencies = [],
        payload_sha512 = hash(payload),
        batcher_public_key = public_key,
        nonce = random.random().hex().encode()
    ).SerializeToString()

    # Create a Transaction from the header and payload above.
    transaction = Transaction(
        header = header,
        payload = payload.encode(),                 # encode the payload
        header_signature = signer.sign(header)
    )

    transaction_list = [transaction]

    # Create a BatchHeader from transaction_list above.
    header = BatchHeader(
        signer_public_key = public_key,
        transaction_ids = [txn.header_signature for txn in transaction_list]
    ).SerializeToString()

    # Create Batch using the BatchHeader and transaction_list above.
    batch = Batch(
        header = header,
        transactions = transaction_list,
        header_signature = signer.sign(header)
    )

    # Create a Batch List from Batch above
    batch_list = BatchList(batches=[batch])
    batch_id = batch_list.batches[0].header_signature
    # Send batch_list to the REST API
    result = send_to_rest_api("batches", batch_list.SerializeToString(), 'application/octet-stream')

    # Wait until transaction status is COMMITTED, error, or timed out
    return wait_for_status(batch_id, result, wait = wait)

if __name__ == '__main__':
    try:
        opts, args = parser.parse_args()
        base_url = opts.url
        if sys.argv[1] == "addManufacturer":
            logging.info ('add manufacture command: ' + sys.argv[2])
            result = addManufacturer(sys.argv[2])
            if result == 'COMMITTED':
                logging.info (sys.argv[2] + " added.")
                print ("Added " + sys.argv[2])
            else:
                logging.info (sys.argv[2] + " not added.")
                print ("\n{} not added ".format(sys.argv[2]))
        elif sys.argv[1] == "addDistributer":
            logging.info ('add distributer command: ' + sys.argv[2])
            result = addDistributer(sys.argv[2])
            if result == 'COMMITTED':
                logging.info (sys.argv[2] + " added.")
                print ("Added " + sys.argv[2])
            else:
                logging.info (sys.argv[2] + " not added.")
                print ("\n{} not added ".format(sys.argv[2]))
        elif sys.argv[1] == "addPharmacy":
            logging.info ('add Pharmacy command: ' + sys.argv[2])
            result = addPharmacy(sys.argv[2])
            if result == 'COMMITTED':
                logging.info (sys.argv[2] + " added.")
                print ("Added " + sys.argv[2])
            else:
                logging.info (sys.argv[2] + " not added.")
                print ("\n{} not added ".format(sys.argv[2]))
        elif sys.argv[1] == "manufacture":
            logging.info ('manufacture command: ' + sys.argv[2])
            result = manufacture(sys.argv[2], sys.argv[3])
            if result == 'COMMITTED':
                logging.info (sys.argv[2] + " manufactured.")
                print ("Manufactured " + sys.argv[2])
            else:
                logging.info (sys.argv[2] + " not manufactured.")
                print ("\n{} not manufctured ".format(sys.argv[3]))
        elif sys.argv[1] == "giveto":
            logging.info ('giveto command: distributer: {}, medicine: {}'.format(sys.argv[2], sys.argv[3]))
            result = giveToDistributor(sys.argv[2], sys.argv[3], sys.argv[4])
            if result == 'COMMITTED':
                logging.info ('Distributed - distributer: {}, medicine: {}'.format(sys.argv[2], sys.argv[3]))
                print ('Distributed - distributer: {}, medicine: {}'.format(sys.argv[2], sys.argv[3]))
            else:
                logging.info ("Didn't Distributed - distributer: {}, medicine: {}".format(sys.argv[2], sys.argv[3]))
                print ("Didn't Distributed - distributer: {}, medicine: {}".format(sys.argv[2], sys.argv[3]))
        elif sys.argv[1] == "listManufacturers":
            logging.info ('command : listManufacturers')
            result = listClients(MANUFACTURERS_TABLE)
            print ('The Manufacturers: {}'.format (result))
        elif sys.argv[1] == "listDistributers":
            logging.info ('command : listDistributers')
            result = listClients(DISTRIBUTERS_TABLE)
            print ('The Distributers: {}'.format (result))
        elif sys.argv[1] == "listPharmacies":
            logging.info ('command : listPharmacies')
            result = listClients(PHARMACY_TABLE)
            print ('The Pharmacies: {}'.format (result))
        elif sys.argv[1] == "seeManufacturer":
            logging.info ('command : seeManufacturer')
            address = getManufacturerAddress(sys.argv[2])
            result = listClients(address)
            print ('content: {}'.format (result))
        elif sys.argv[1] == "seeDistributer":
            logging.info ('command : seeDistributer')
            address = getDistributerAddress(sys.argv[2], 'request')
            result = listClients(address)
            print ('content: {}'.format (result))
        else:
            print ('Invalid command.\nValid commands: \n\taddManufacturer manufacturerName, addDistributer name, \n\tmanufacture mname medicine name, giveto mname dname medicineName, \n\tlistManufacturers, listDistributers, seeManufacturer mname, seeDistributer dname')
    except IndexError as i:
        logging.debug ('Invalid command')
        print ('Invalid command.\nValid commands: \n\taddManufacturer manufacturerName, addDistributer name, \n\tmanufacture mname medicine name, giveto mname dname medicineName, \n\tlistManufacturers, listDistributers, seeManufacturer mname, seeDistributer dname')
        print (i)
    except Exception as e:
        print (e)
