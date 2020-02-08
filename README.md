# Rich Context Server

This provides browser-based search and discovery for the Rich Context
knowledge graph, including:

  - web app based on Flask
  - UI based on PureCSS
  - API based on OpenAPI/Swagger


## Install

```
pip install -r requirements.txt
```

This web app requires a `flask.cfg` config file, which is not
committed for security reason. You must create your own before running
the web app. Parameters required in the configuration file include:

```
DEBUG = False
MAX_CONTENT_LENGTH = 52428800
SECRET_KEY = "place some secret here"
SEND_FILE_MAX_AGE_DEFAULT = 3000
```


## Launch

```
python app.py
```

...then load `http://localhost:5000/` in your browser.

See `python app.py --help` for a list of command line options


## Full Graph

To launch with the full knowledge graph, first download the latest
JSON-LD file for the graph from

  - <https://storage.googleapis.com/rich-context/tmp.jsonld>

Next, pre-compute the links for the KG:

```
python app.py --pre true --corpus tmp.jsonld 
```

That updates the `precomp.json` file, which the web app loads whenever
it gets launched.

Then re-launch the web app.
