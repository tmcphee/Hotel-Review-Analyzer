from google.cloud import storage
from storage_list_files import return_blobs
from storage_create_bucket import create_bucket
from storage_upload_file import upload_blob

import os
import binascii
import collections
import datetime
import hashlib
import sys

# pip install google-auth
from google.oauth2 import service_account
# pip install six
import six
from six.moves.urllib.parse import quote


def get_cred_path(host):
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    if host == "127.0.0.1":
        return os.path.join(ROOT_DIR, "credentials.json")
    else:
        return os.path.join("config", "credentials.json")


def create_bk(bucket_name, host):
    credpath = get_cred_path(host)
    try:
        storage_client = storage.Client()
        storage_client.from_service_account_json(credpath)
        bucket = storage_client.create_bucket(bucket_name)
        print("Bucket {} created".format(bucket_name))
        return True
    except Exception as e:
        print("Bucket name is either existing or invalid format -> ".format(e))
        return False


def upload_file(path, name, bucket_name, host):
    credpath = get_cred_path(host)
    storage_client = storage.Client()
    storage_client.from_service_account_json(credpath)
    bucket = storage_client.bucket(bucket_name)

    blob = bucket.blob(path)
    blob.upload_from_filename(name)


def download_file(path, name, bucket_name, host):
    credpath = get_cred_path(host)
    storage_client = storage.Client()
    storage_client.from_service_account_json(credpath)
    bucket = storage_client.bucket(bucket_name)

    blob = bucket.blob(path)
    blob.download_to_filename(name)


def get_signed_url(path, name, bucket_name, host):
    credpath = get_cred_path(host)
    storage_client = storage.Client()
    storage_client.from_service_account_json(credpath)
    bucket = storage_client.bucket(bucket_name)

    file = bucket.file()


def list_files(bucket_name, host):
    credpath = get_cred_path(host)
    blob_names = []
    storage_client = storage.Client()
    storage_client.from_service_account_json(credpath)
    blobs = storage_client.list_blobs(bucket_name)

    for blob in blobs:
        blob_names.append(blob.name)

    return blob_names


def generate_signed_url(service_account_file, bucket_name, object_name,
                        subresource=None, expiration=604800, http_method='GET',
                        query_parameters=None, headers=None):

    if expiration > 604800:
        print('Expiration Time can\'t be longer than 604800 seconds (7 days).')
        sys.exit(1)

    escaped_object_name = quote(six.ensure_binary(object_name), safe=b'/~')
    canonical_uri = '/{}'.format(escaped_object_name)

    datetime_now = datetime.datetime.utcnow()
    request_timestamp = datetime_now.strftime('%Y%m%dT%H%M%SZ')
    datestamp = datetime_now.strftime('%Y%m%d')

    google_credentials = service_account.Credentials.from_service_account_file(
        service_account_file)
    client_email = google_credentials.service_account_email
    credential_scope = '{}/auto/storage/goog4_request'.format(datestamp)
    credential = '{}/{}'.format(client_email, credential_scope)

    if headers is None:
        headers = dict()
    host = '{}.storage.googleapis.com'.format(bucket_name)
    headers['host'] = host

    canonical_headers = ''
    ordered_headers = collections.OrderedDict(sorted(headers.items()))
    for k, v in ordered_headers.items():
        lower_k = str(k).lower()
        strip_v = str(v).lower()
        canonical_headers += '{}:{}\n'.format(lower_k, strip_v)

    signed_headers = ''
    for k, _ in ordered_headers.items():
        lower_k = str(k).lower()
        signed_headers += '{};'.format(lower_k)
    signed_headers = signed_headers[:-1]  # remove trailing ';'

    if query_parameters is None:
        query_parameters = dict()
    query_parameters['X-Goog-Algorithm'] = 'GOOG4-RSA-SHA256'
    query_parameters['X-Goog-Credential'] = credential
    query_parameters['X-Goog-Date'] = request_timestamp
    query_parameters['X-Goog-Expires'] = expiration
    query_parameters['X-Goog-SignedHeaders'] = signed_headers
    if subresource:
        query_parameters[subresource] = ''

    canonical_query_string = ''
    ordered_query_parameters = collections.OrderedDict(
        sorted(query_parameters.items()))
    for k, v in ordered_query_parameters.items():
        encoded_k = quote(str(k), safe='')
        encoded_v = quote(str(v), safe='')
        canonical_query_string += '{}={}&'.format(encoded_k, encoded_v)
    canonical_query_string = canonical_query_string[:-1]  # remove trailing '&'

    canonical_request = '\n'.join([http_method,
                                   canonical_uri,
                                   canonical_query_string,
                                   canonical_headers,
                                   signed_headers,
                                   'UNSIGNED-PAYLOAD'])

    canonical_request_hash = hashlib.sha256(
        canonical_request.encode()).hexdigest()

    string_to_sign = '\n'.join(['GOOG4-RSA-SHA256',
                                request_timestamp,
                                credential_scope,
                                canonical_request_hash])

    # signer.sign() signs using RSA-SHA256 with PKCS1v15 padding
    signature = binascii.hexlify(
        google_credentials.signer.sign(string_to_sign)
    ).decode()

    scheme_and_host = '{}://{}'.format('https', host)
    signed_url = '{}{}?{}&x-goog-signature={}'.format(
        scheme_and_host, canonical_uri, canonical_query_string, signature)

    return signed_url


def get_signed_url_credfile(host, bucket_name, object_name):
    credpath = get_cred_path(host)
    return generate_signed_url(
        service_account_file=credpath,
        http_method='GET', bucket_name=bucket_name,
        object_name=object_name, subresource=None,
        expiration=604800)


def web_list_blobs(host, bucket_name):
    liststr = ""
    for x in list_files(bucket_name, host):
        url = get_signed_url_credfile(host, bucket_name, x)
        liststr += "<a download=\"text\" href=\"" + url + "\">"
        liststr += x
        liststr += "</a><br>"

    return liststr



