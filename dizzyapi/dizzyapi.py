"""
Library for communicating with the DizzyJam API.
Requires Python 2.6 or above.
"""

from urllib2 import urlopen, URLError, HTTPError, Request
from urllib import urlencode
from ssl import SSLError
import time
import hmac, hashlib
import json
import xml.etree.ElementTree as ET

from dizzyapi.poster.encode import MultipartParam, multipart_encode
from dizzyapi.poster.streaminghttp import register_openers

# Needed to initialize the Poster library
register_openers()

import logging
LOG = logging.getLogger(__name__)
if not LOG.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter (logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    LOG.addHandler (handler)
    LOG.setLevel(logging.WARN)


SOCK_TIMEOUT = 120
UA = 'DizzyJam Python API Lib v1.0'
ENC = 'utf8'

# Subdict helper func with a twist - ignores keys with None values
subdict = lambda args,l: dict([(arg,l[arg]) for arg in args if l[arg] is not None])

def url_uencode (d):
    """
    Workaround against the lame urlencode implementation in Python, which
    panics when it receives an unicode string with non-ascii encoding.
    """
    strdict = {}
    for k,v in d.iteritems():
        try:
            k = str(k)
        except UnicodeEncodeError:
            k = unicode(k).encode(ENC)
        try:
            v = str(v)
        except UnicodeEncodeError:
            v = unicode(v).encode(ENC)
        strdict[k] = v
    return urlencode(strdict)

class APIError (Exception):
    """
    Custom Exception class to mark errors coming from the API Communication.
    """
    def __init__ (self, code, message):
        self.code = code
        self.message = message
        LOG.critical (message)
    def __str__ (self):
        return '%s: %s' % (self.code, repr(self.message))

class _APIConn (object):
    """
    Connection object using the JSON data format.
    """
    VER = '1'
    SUFFIX = ''
    BASE_URL = """https://www.dizzyjam.com/api/v%(ver)s/%(method)s.%(suffix)s%(api_args)s"""

    def __init__ (self, client_id = None, token = None, ver = None, base_url = None):
        """
        All parameters are optional. The API functions will raise an error if
        you try to do authenticated calls without setting client_id and token
        beforehand.
        """
        self.client_id = client_id
        self.token = token
        self.base_url = base_url or self.BASE_URL
        self.ver = ver or self.VER

    def _itemdict (self, items):
        """
        Generates a dictionary suitable for merging into an API call
        based on the supplied list of items.
        Each list element should have the following keys:
        - product_id
        - colour_id
        - size
        - quantity
        """
        keys = ('product_id', 'colour_id', 'size','quantity')
        result = {}
        for n, item in enumerate(items):
            prefix = 'item%d_' % n
            for key in keys:
                result[prefix + key] = item[key]
        return result

    def call_raw (self,method, argdict = {}, filedict = {}):
        """
        Worker function that handles the actual HTTP call and formatting.
        """
        data = None
        headers = {'User-Agent': UA}
        try:
            api_args = u'?'+ url_uencode(argdict) if argdict else ''
            url = self.base_url % {'ver':self.ver, 'suffix':self.SUFFIX,
                                   'method':method, 'api_args':api_args,}
            LOG.debug('Generated request URL: %s' % url)
            # handle file uploads using the Poster module
            if filedict:
                for k,v in filedict.iteritems():
                    if not hasattr(v,'name'):
                        raise ValueError('File %s does not have a "name" property!' % k)
                params = MultipartParam.from_params (filedict)
                data, newheaders = multipart_encode(params)
                headers.update(newheaders)
            req = Request (url, data, headers = headers)
            result = urlopen(req, timeout=SOCK_TIMEOUT).read()
            LOG.debug('Generated raw result: %s' % result)
        except (URLError, HTTPError, SSLError), err:
            raise APIError (0, str(err))

        return self.process_result(result)

    def get_sign (self, method, argdict):
        """
        Returns the authentication signature value. The keys `auth_id` and
        `auth_ts` must already be present in argdict.
        """
        sig_base = u'v%s/%s?' % (self.ver, method)
        sig_base += u'&'.join(unicode(key) + u'=' + unicode(argdict[key]) for key in sorted(argdict.keys()))
        sig = hmac.new(self.token, sig_base, digestmod = hashlib.sha256).hexdigest()
        return sig


    def call_auth (self, method, argdict = {}):
        """
        Worker function that adds authentication parameters to the call. It also extracts the
        *_file keys from the other args, in order to enable special processing as filedict arg.
        """
        if not self.client_id or not self.token:
            raise ValueError("Call %s is authenticated, and authenticated calls require both UserID and Token" % method)
        argdict['auth_id'] = self.client_id
        argdict['auth_ts'] = int(time.time())
        filedict = dict([(k, argdict.pop(k)) for k in argdict.keys() if k.endswith('_file')])
        argdict['auth_sig'] = self.get_sign (method, argdict)
        return self.call_raw (method, argdict, filedict)



    def process_result(self, result):
        """
        Must be overridden by the format-specific implementation.
        """
        raise NotImplementedError

    def dj_catalogue_stores (self, count = None, start = None):
        """
        Lists available stores.
        """
        method = 'catalogue/stores'
        api_args = subdict (['count', 'start'], locals())
        return self.call_raw (method, api_args)

    def dj_catalogue_store_info(self, store_id, country = None, count = None, start = None):
        """
        Details about a store, including the available products.
        """
        method = 'catalogue/store_info'
        api_args = subdict (['store_id','country','count', 'start'], locals())
        return self.call_raw (method, api_args)

    def dj_catalogue_product_info (self, product_id, country = None):
        """
        Details about a product.
        """
        method='catalogue/product_info'
        api_args = subdict (['product_id', 'country'], locals())
        return self.call_raw (method, api_args)

    def dj_order_calculate (self, items, country = None):
        """
        Creates an order with the provided items. Items is a list of dictionaries.
        Each list element should have the following keys:
        - product_id
        - colour_id
        - size
        - quantity
        """
        method='order/calculate'
        api_args = subdict (['country'], locals())
        api_args.update (self._itemdict(items))
        return self.call_auth (method, api_args)

    def dj_order_checkout (self, name, email, address_1, city, region, postcode, country,
                           items, return_url, address_2 = None, mobile = None, checkout = None):
        """
        Does an order checkout with the supplied arguments.

        Each element in the items list of dicts should have the following keys:
        - product_id
        - colour_id
        - size
        - quantity
        """
        method = 'order/checkout'
        api_args = subdict (['name', 'email','address_1','city', 'region', 'postcode',
                             'country','return_url', 'address_2','mobile', 'checkout'],
                            locals())
        api_args.update (self._itemdict(items))
        return self.call_auth (method, api_args)

    def dj_manage_create_product (self, store_id, product_type_id, process, name, colours = None,
                                  featured_colour = None, design_id = None, design_file = None,
                                  scale = None, horiz = None, vert = None):
        """
        Creates a new product under the given Store
        """

        method = 'manage/create_product'
        api_args = subdict (['store_id', 'product_type_id','process','name', 'colours',
                             'featured_colour', 'design_id','design_file', 'scale',
                             'horiz', 'vert'],
                            locals())
        return self.call_auth (method, api_args)

    def dj_manage_delete_product (self, product_id):
        """
        Deletes the provided product.
        """
        method = 'manage/delete_product'
        api_args = subdict (['product_id'],locals())
        return self.call_auth (method, api_args)


    def dj_manage_product_options (self, store_id):
        """
        Retrieves the product options from the given store.
        """
        method = 'manage/product_options'
        api_args = subdict (['store_id'],locals())
        return self.call_auth (method, api_args)

    def dj_manage_store_options (self):
        """
        Retrieves the available store-level options.
        """
        method = 'manage/store_options'
        return self.call_auth (method, {})

    def dj_manage_create_store (self, store_id, name, description = None, logo_file = None,
                                genres = None, website = None, myspace_url = None,
                                facebook_url = None, twitter_id = None,
                                rss_feed_url = None, user_id = None):
        """
        Creates a new store.
        """
        method = 'manage/create_store'
        api_args = subdict (['store_id','name', 'description', 'logo_file',
                            'genres', 'website', 'myspace_url', 'facebook_url',
                            'twitter_id', 'rss_feed_url', 'user_id'], locals())
        return self.call_auth (method, api_args)

    def dj_manage_edit_store (self, store_id, name, description = None, logo_file = None,
                                genres = None, website = None, myspace_url = None,
                                facebook_url = None, twitter_id = None, rss_feed_url = None,
                                clear = None):
        """
        Updates the settings of an existing store.
        """
        method = 'manage/edit_store'
        api_args = subdict (['store_id','name', 'description', 'logo_file',
                            'genres', 'website', 'myspace_url', 'facebook_url',
                            'twitter_id', 'rss_feed_url', 'clear'], locals())
        return self.call_auth (method, api_args)


    def dj_manage_delete_store (self, store_id):
        """
        Deletes a store.
        """
        method = 'manage/delete_store'
        api_args = subdict (['store_id'],locals())
        return self.call_auth (method, api_args)


    def dj_manage_my_stores (self, user_id = None, count = None, start = None):
        """
        Retrieve a list of the stores owned by the authenticated user.
        """
        method = 'manage/my_stores'
        api_args = subdict (['user_id', 'count','start'],locals())
        return self.call_auth (method, api_args)

    def dj_manage_my_users (self, count = None, start = None):
        """
        Retrieve the subusers
        """
        method = 'manage/my_users'
        api_args = subdict (['count','start'],locals())
        return self.call_auth (method, api_args)

    def dj_manage_create_user (self, email, password = None, name = None):
        method = 'manage/create_user'
        api_args = subdict (['email', 'password','name'],locals())
        return self.call_auth (method, api_args)

class JSONAPIConn (_APIConn):
    """
    API connection class that uses JSON and returns
    Python structs (dicts, lists) as responses.
    """
    SUFFIX = 'json'
    def process_result (self, res_str):
        try:
            data = json.loads(res_str)
        except Exception, err:
            LOG.critical("Can't parse json response:%s" % res_str)
            raise APIError (0, err)
        if not 'success' in data:
            raise APIError (0, 'Response does not contain a successful flag!')
        if not data['success']:
            raise APIError (data.get('errorCode',0), '%s. (details: %s)' %
                                (data.get('error'), data.get('errorDetails') or data.get('event_id')))
        return data

class XMLAPIConn (_APIConn):
    """
    API connection class that uses XML and returns an ElementTree root node
    as a response.
    """
    SUFFIX = 'xml'
    def process_result (self, res_str):
        try:
            root = ET.fromstring (res_str)
        except Exception, err:
            raise APIError (0, err)
        success = root.find ('success')
        if success is None:
            raise APIError (0, 'Response does not contain a successful flag!')
        if not success.text.lower() == 'true':
            code = int(root.findtext ('errorCode'))
            error = root.findtext ('error')
            details = root.findtext ('errorDetails')
            raise APIError (code, '%s %s' % (error, '' + str(details) if details else ''))
        return root
