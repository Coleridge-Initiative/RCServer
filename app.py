#!/usr/bin/env python
# encoding: utf-8

from bs4 import BeautifulSoup
from flasgger import Swagger
from flask import Flask, g, \
    jsonify, make_response, redirect, render_template, render_template_string, request, \
    safe_join, send_file, send_from_directory, session, url_for
from flask_caching import Cache
from http import HTTPStatus
from pathlib import Path
from richcontext import server as rc_server
import argparse
import codecs
import diskcache as dc
import hashlib
import json
import os
import string
import sys
import tempfile
import time


DEFAULT_PORT = 5000
DEFAULT_CORPUS = "min_kg.jsonld"


######################################################################
## app definitions

APP = Flask(__name__, static_folder="static", template_folder="templates")
APP.config.from_pyfile("flask.cfg")

CACHE = Cache(APP, config={"CACHE_TYPE": "simple"})
DC_CACHE = dc.Cache("/tmp/richcontext")

NET = rc_server.RCNetwork()
LINKS = {}


######################################################################
## page routes

@APP.route("/")
def home_page ():
    return render_template("index.html")


@APP.route("/index.html")
@APP.route("/home/")
def home_redirects ():
    return redirect(url_for("home_page"))

## CSS, JavaScript
@APP.route("/css/pure-min.css")
@APP.route("/css/grids-responsive-min.css")
@APP.route("/css/vis.css")
@APP.route("/js/vis-network.min.js")

## other well-known routes
@APP.route("/favicon.png")
@APP.route("/apple-touch-icon.png")
def static_from_root ():
    return send_from_directory(APP.static_folder, request.path[1:])


######################################################################
## utilities

def get_hash (strings, prefix=None, digest_size=10):
    """
    construct a unique identifier from a collection of strings
    """
    m = hashlib.blake2b(digest_size=digest_size)
    
    for elem in sorted(map(lambda x: x.encode("utf-8").lower().strip(), strings)):
        m.update(elem)

    if prefix:
        id = prefix + m.hexdigest()
    else:
        id = m.hexdigest()

    return "".join(filter(lambda x: x in string.printable, id))


######################################################################
## OpenAPI support

API_TEMPLATE = {
        "swagger": "2.0",
        "info": {
            "title": "Rich Context",
            "description": "OpenAPI for Rich Context microservices",
            "contact": {
                "responsibleOrganization": "Coleridge Initiative",
                "name": "API Support",
                "url": "https://coleridgeinitiative.org/richcontext"
            },
            "termsOfService": "https://coleridgeinitiative.org/computing"
        },
        "basePath": "/",
        "schemes": ["http"],
        "externalDocs": {
            "description": "Documentation",
            "url": "https://github.com/Coleridge-Initiative/rclc/wiki"
        }
    }


SWAGGER = Swagger(APP, template=API_TEMPLATE)


######################################################################
## API routes

@CACHE.cached(timeout=3000)
@APP.route("/api/v1/query/<radius>/<entity>", methods=["GET"])
def api_entity_query (radius, entity):
    """
    query a subgraph for an entity
    ---
    tags:
      - knowledge_graph
    description: 'query with a radius near an entity, using BFS'
    parameters:
      - name: radius
        in: path
        required: true
        type: integer
        description: radius for BFS neighborhood
      - name: entity
        in: path
        required: true
        type: string
        description: entity name to search
    produces:
      - application/json
    responses:
      '200':
        description: neighborhood search within the knowledge graph
    """
    global DC_CACHE, NET

    t0 = time.time()
    handle, html_path = tempfile.mkstemp(suffix=".html", prefix="rc_hood", dir="/tmp")
    cache_token = get_hash([ entity, radius ], prefix="hood-")

    subgraph = NET.get_subgraph(search_term=entity, radius=int(radius))
    hood = NET.extract_neighborhood(subgraph, entity, html_path)

    with open(html_path, "r") as f:
        html = f.read()
        DC_CACHE[cache_token] = html
        #soup = BeautifulSoup(html, "html.parser")
        #node = soup.find("body").find("script")
        #DC_CACHE[cache_token] = node.text
    
    os.remove(html_path)

    return hood.serialize(t0, cache_token)


@CACHE.cached(timeout=3000)
@APP.route("/api/v1/graph/<cache_token>", methods=["GET"])
def fetch_graph (cache_token):
    """
    fetch a cached network diagram 
    ---
    tags:
      - knowledge_graph
    description: 'get the JavaScript to render a graph'
    parameters:
      - name: cache_token
        in: path
        required: true
        type: string
        description: token to use for disk cache access
    produces:
      - application/json
    responses:
      '200':
        description: JavaScript to render a graph
    """
    global DC_CACHE, NET

    view = {
        "js": DC_CACHE[cache_token]
        }

    return jsonify(view)


@CACHE.cached(timeout=3000)
@APP.route("/api/v1/links/<index>", methods=["GET"])
def api_entity_links (index):
    """
    lookup the links for an entity
    ---
    tags:
      - knowledge_graph
    description: 'lookup the links for an entity'
    parameters:
      - name: index
        in: path
        required: true
        type: integer
        description: index of entity to lookup
    produces:
      - application/json
    responses:
      '200':
        description: links for an entity within the knowledge graph
    """
    global LINKS, NET

    try:
        id = int(index)
    except:
        id = -1

    html = None

    if id >= 0 and id < len(NET.id_list):
        uuid = NET.id_list[id]

        if uuid in LINKS:
            html = LINKS[uuid]

    return jsonify(html)


@CACHE.cached(timeout=3000)
@APP.route("/api/v1/stuff", methods=["POST"])
def api_post_stuff ():
    """
    post some stuff
    ---
    tags:
      - example
    description: 'post some stuff'
    parameters:
      - name: mcguffin
        in: formData
        required: true
        type: string
        description: some stuff
    produces:
      - application/json
    responses:
      '200':
        description: got your stuff just fine
      '400':
        description: bad request; is the `mcguffin` parameter correct?
    """

    mcguffin = request.form["mcguffin"]
    
    response = {
        "received": mcguffin
        }

    status = HTTPStatus.OK.value

    return jsonify(response), status


@CACHE.cached(timeout=3000)
@APP.route("/graph/<cache_token>", methods=["GET"])
def fetch_graph_html (cache_token):
    """
    fetch the HTML to render a cached network diagram 
    """
    global DC_CACHE

    if cache_token in DC_CACHE:
        html = DC_CACHE[cache_token]
    else:
        html = f"<strong>NOT FOUND: {cache_token}</strong>"

    return render_template_string(html)


######################################################################
## main

def main (args):
    global LINKS, NET

    elapsed_time = NET.load_network(Path(args.corpus))
    print("{:.2f} ms corpus parse time".format(elapsed_time))

    t0 = time.time()

    with codecs.open(Path("links.json"), "wb", encoding="utf8") as f:
        LINKS = NET.render_links(APP.template_folder)
        json.dump(LINKS, f, indent=4, sort_keys=True, ensure_ascii=False)

    print("{:.2f} ms link format time".format((time.time() - t0) * 1000.0))

    APP.run(host="0.0.0.0", port=args.port, debug=True)


if __name__ == "__main__":
    # parse the command line arguments, if any
    parser = argparse.ArgumentParser(
        description="Rich Context: server, API, UI"
        )

    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="web IP port"
        )

    parser.add_argument(
        "--corpus",
        type=str,
        default=DEFAULT_CORPUS,
        help="corpus file as JSON-LD"
        )

    main(parser.parse_args())
