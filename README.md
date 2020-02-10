# Rich Context Server

This provides browser-based search and discovery for the Rich Context
knowledge graph, including:

  - web app based on Flask
  - API based on OpenAPI/Swagger
  - UI based on PureCSS


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
PATH_DC_CACHE = "/tmp/richcontext"
SECRET_KEY = "place some secret here"
SEND_FILE_MAX_AGE_DEFAULT = 3000
```

To install for Ubuntu running on a GCP instance, see `INSTALL.md`


## Command Line Interface

See `python app.py --help` for a list of command line options


## Launch

```
python app.py
```

...then load `http://localhost:5000/` in your browser.

Alternatively, you can run `gunicorn` to get a WSGI-compliant server:

```
gunicorn -w 4 -b 127.0.0.1:5000 wsgi:APP
```


## Full Graph

To launch with the full knowledge graph, first download the latest
JSON-LD file for the graph from:

  - <https://storage.googleapis.com/rich-context/tmp.jsonld>

Next, pre-compute the links for the KG:

```
python app.py --pre true --corpus tmp.jsonld 
```

That rewrites the `precomp.json` file, which the web app loads to
populate its data structures for the KG whenever it gets launched.

Then re-launch the web app.


## Web Tokens

To generate web tokens for identifying HITL feedback from known users,
first prepare a TSV file such as:

```
email	expiry	roles
foo@agency.gov	731	agency
kim@ci.org	5000	ci,ops
```

The input file is tab delimited and expected to have a header row,
where the columns are:

  - *email:* email address for the user
  - *expiry:* how long the web token will be valid (in days)
  - *roles:* role descriptions (comma delimited)

The allowed roles must be from:

  - `agency`	- agency staff
  - `ci`	- Coleridge Initiative staff
  - `expert`	- external expert (outside of an agency)
  - `ops`	- operations for running the Rich Context web app

For example, if we've saved that file to `usda.tsv` then run
the CLI to generate web tokens:

```
python app.py --token usda.tsv 
```

That will save the generated web tokens to a file `token.txt` along
with their decrypted payloads, for example:

```
{'id': 'foo@agency.gov', 'roles': ['agency']}

eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ1cm46Y29sZXJpZGdlaW5pdGlhdGl2ZS5vcmc6cmljaGNvbnRleHQiLCJleHAiOjE2NDQ0Mjk1MDYsInNjbyI6eyJpZCI6ImZvb0BhZ2VuY3kuZ292Iiwicm9sZXMiOlsiYWdlbmN5Il19fQ.zAPYZJpuAkgPN5P7EqEbAVzBn2sV7THzQEvGJGAWbHg
```

Then provide the generated web token (long hex string) to each of the
Rich Context users. These are very long strings, so be careful about
handling line breaks -- that you don't introduce bad characters.

The users will each need to enter their web token into the `Configure`
page from their browser.

