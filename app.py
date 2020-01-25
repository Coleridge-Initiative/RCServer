#!/usr/bin/env python
# encoding: utf-8

from flasgger import Swagger
from flask import Flask, g, jsonify, make_response, redirect, render_template, request
from flask_caching import Cache
from http import HTTPStatus
import json
import sys


######################################################################
## app definitions

APP = Flask(__name__, static_folder="static", template_folder="templates")
APP.config.from_pyfile("flask.cfg")

CACHE = Cache(APP, config={"CACHE_TYPE": "simple"})


@APP.route("/")
def home_page ():
    return "hello"

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
                "responsibleOrganization": "NYU Coleridge Initiative",
                "name": "API Support",
                "url": "https://coleridgeinitiative.org/connecting"
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

@APP.route("/api/v1/info")
def api_get_info ():
    """
    get API info
    ---
    tags:
      - info
    description: 'get info about this API'
    produces:
      - application/json
    responses:
      '200':
        description: info about this API
    """

    return jsonify({
        "neighborhood": "Mr. Rogers",
        "status": "beautiful day",
    })


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
    PORT = 5000
    APP.run(host="0.0.0.0", port=PORT, debug=True)


if __name__ == "__main__":
    main()
