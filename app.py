#!/usr/bin/env python
# encoding: utf-8

from pathlib import Path
from flasgger import Swagger
from flask import Flask, g, jsonify, make_response, redirect, render_template, request
from flask_caching import Cache
from http import HTTPStatus
from richcontext import server as rc_server
import json
import sys
import time


######################################################################
## app definitions

APP = Flask(__name__, static_folder="static", template_folder="templates")
APP.config.from_pyfile("flask.cfg")

CACHE = Cache(APP, config={"CACHE_TYPE": "simple"})

t0 = time.time()
NET = rc_server.RCNetwork.load_network(Path("min_kg.jsonld"))
NET_TIME = (time.time() - t0) * 1000.0


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
## OpenAPI support

API_TEMPLATE = {
        "swagger": "2.0",
        "info": {
            "title": "demo Flask + Swagger for a microservice",
            "description": "demo Flask + Swagger for a microservice",
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
            "url": "https://coleridgeinitiative.org/richcontext"
        }
    }


SWAGGER = Swagger(APP, template=API_TEMPLATE)


######################################################################
## API routes

@APP.route("/api/v1/query/<radius>/<query>", methods=["GET"])
def api_query (radius, query):
    """
    get API info
    ---
    tags:
      - info
    description: 'get info about this API'
    parameters:
      - name: radius
        in: path
        required: true
        type: integer
        description: radius for BFS neighborhood
      - name: query
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
    global NET

    print("|{}| {}".format(query, radius))

    t0 = time.time()
    subgraph = NET.get_subgraph(search_term=query, radius=int(radius))
    hood = NET.extract_neighborhood(subgraph, query)

    return hood.serialize(t0)


@CACHE.cached(timeout=3000)
@APP.route("/api/v1/stuff", methods=["POST"])
def api_post_stuff ():
    """
    post some stuff
    ---
    tags:
      - uri
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

def main ():
    print("{:.2f} ms KG parse time".format(NET_TIME))

    PORT = 5000
    APP.run(host="0.0.0.0", port=PORT, debug=True)


if __name__ == "__main__":
    main()
