#!/usr/bin/env python
# encoding: utf-8

from bs4 import BeautifulSoup
from flasgger import Swagger
from flask import Flask, g, jsonify, make_response, redirect, render_template, render_template_string, request
from flask_caching import Cache
from http import HTTPStatus
from pathlib import Path
from richcontext import server as rc_server
import argparse
import diskcache as dc
import hashlib
import json
import string
import sys
import time


DEFAULT_PORT = 5000
DEFAULT_CORPUS = "min_kg.jsonld"


######################################################################
## app definitions

APP = Flask(__name__, static_folder="static", template_folder="templates")
APP.config.from_pyfile("flask.cfg")

CACHE = Cache(APP, config={"CACHE_TYPE": "simple"})
NET = rc_server.RCNetwork()

DC_CACHE = dc.Cache("/tmp/richcontext")


######################################################################
## page routes

@APP.route("/")
def home_page ():
    return render_template("index.html")


@APP.route("/index.html")
@APP.route("/home/")
def home_redirects ():
    return redirect(url_for("home_page"))


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
    global NET, DC_CACHE

    t0 = time.time()
    subgraph = NET.get_subgraph(search_term=entity, radius=int(radius))
    hood, filename = NET.extract_neighborhood(subgraph, entity)

    cache_token = get_hash([ entity, radius ], prefix="hood-")

    with open("corpus.html", "r") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
        node = soup.find("body").find("script")
        DC_CACHE[cache_token] = node.text
    
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
    global NET, DC_CACHE

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
    global NET, DC_CACHE

    try:
        id = int(index)
    except:
        id = -1

    if id >= 0 and id < len(NET.id_list):
        result = NET.id_list[id]
    else:
        result = None

    return jsonify(result)


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


######################################################################
## main

def main (args):
    global NET

    elapsed_time = NET.load_network(Path(args.corpus))
    print("{:.2f} ms corpus parse time".format(elapsed_time))

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
        help="corpus file"
        )

    main(parser.parse_args())
