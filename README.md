dizzyapi-py
===========
This library provides a Python client for the [DizzyJam.com API](http://www.dizzyjam.com/apidoc/). The _catalogue/_ group of calls is public, and can be used without authentication; all other calls require valid _AuthID_ and _API Key_. Information on obtaining these credentials can be found in the [API Docs](http://www.dizzyjam.com/apidoc/).

This library supports both JSON and XML as API outputs.

## Installation
Simply drop the _dizzyapi_ package where Python can find it. There are no external dependencies. Requires Python 2.6+.

## Usage
Instantiate a connection object and call its methods:
```python

from dizzyapi import JSONAPIConn, XMLAPIConn, APIError

# Unauthenticated JSON connection
# API results are returned as Python dictionaries
json_conn = JSONAPIConn()
store_info = json_conn.dj_catalogue_store_info ('dizzyjam')

# Authenticated JSON - requires valid AuthID and APIKey
json_conn = JSONAPIConn(AuthID, APIKey)
my_stores = json_conn.dj_manage_my_stores() # Result would still be a dict

# Method names stay the same between JSON and XML connections
# API results are returned as ElementTrees (xml.etree.ElementTree)
xml_conn = XMLAPIConn()
store_info = xml_conn.dj_catalogue_store_info ('dizzyjam')
```
## More info
The full list of calls supported by the API, along with their arguments and 
sample output can be found at http://www.dizzyjam.com/apidoc/. To get the 
corresponding library method name, simply prefix the call name with 'dj_' and 
replace '/' with '_' (e.g. _catalogue/store_info_ -> _dj_catalogue_store_info()_)
