#!/usr/bin/env python
# encoding: utf-8

from flasgger import Swagger
from flask import Flask, g, \
    jsonify, make_response, redirect, render_template, render_template_string, \
    request, safe_join, send_file, send_from_directory, session, url_for
from flask_caching import Cache
from http import HTTPStatus
from pathlib import Path
from richcontext import server as rc_server
import argparse
import codecs
import copy
import datetime
import diskcache as dc
import hashlib
import json
import jwt
import os
import string
import sys
import tempfile
import time


######################################################################
## web app definitions

class RCServerApp (Flask):
    DEFAULT_CORPUS = "min_kg.jsonld"
    DEFAULT_EXPIRY = 731 # two years in days
    DEFAULT_PORT = 5000
    DEFAULT_PRECOMPUTE = False
    DEFAULT_TOKEN = None

    AGENCY_SCOPE = {
        "id": "email@agency.gov",
        "roles": ["agency"]
        }

    ADMIN_SCOPE = {
        "id": "admin",
        "roles": ["admin"]
        }

    PATH_DC_CACHE = "/tmp/richcontext"
    JWT_ISSUER = "urn:coleridgeinitiative.org:richcontext"
    LEEWAY_DELTA = datetime.timedelta(minutes=3)


    def __init__ (self, name):
        """
        initialize the web app
        """
        super(RCServerApp, self).__init__(name, static_folder="static", template_folder="templates")
        self.config.from_pyfile("flask.cfg")

        self.net = rc_server.RCNetwork()
        self.disk_cache = dc.Cache(self.PATH_DC_CACHE)
        self.links = {}
        self.corpus_path = Path(self.DEFAULT_CORPUS)


    def run (self, host=None, port=None, debug=None, load_dotenv=True, **options):
        """
        pre-compute links from the given corpus file
        """
        elapsed_time = self.net.load_network(self.corpus_path)
        print("{:.2f} ms corpus parse time".format(elapsed_time))

        t0 = time.time()
        self.links = self.net.render_links(self.template_folder)
        print("{:.2f} ms link format time".format((time.time() - t0) * 1000.0))

        with codecs.open(Path("links.json"), "wb", encoding="utf8") as f:
            json.dump(self.links, f, indent=4, sort_keys=True, ensure_ascii=False)

        # call the super.run()
        super(RCServerApp, self).run(host=host, port=port, debug=debug, load_dotenv=load_dotenv, **options)


    @classmethod
    def get_hash (cls, strings, prefix=None, digest_size=10):
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


    @classmethod
    def jwt_encode (cls, key, expiry, scopes):
        """
        encode a JWT payload for a web token
        """
        payload = {
            "iss": cls.JWT_ISSUER,
            "exp": datetime.datetime.utcnow() + expiry,
            "sco": scopes
            }

        return jwt.encode(payload, key, algorithm="HS256").decode("utf-8")


    @classmethod
    def jwt_decode (cls, key, token):
        """
        decode and verify a JWT payload for a web token
        """
        payload = jwt.decode(
            token, 
            key,
            algorithms=["HS256"],
            leeway=cls.LEEWAY_DELTA,
            issuer=cls.JWT_ISSUER
            )

        return payload["sco"]


    def extract_query_home (self, request):
        """
        extract and validate the query parameters from an HTTP request
        """
        query = request.args.to_dict()
    
        if "entity" in query:
            query["entity"] = query["entity"].strip()

            # TODO: remove invalid or unknown entity names
            if len(query["entity"]) < 1:
                del query["entity"]

        if "radius" in query:
            try:
                radius = int(query["radius"].strip())
            except:
                # force a valid radius value
                radius = 2
            finally:          
                query["radius"] = str(radius)

        return query


    def run_entity_query (self, radius, entity):
        """
        run a neighborhood query for the given entity and radius
        """
        t0 = time.time()
        entity = entity.strip()

        try:
            radius_val = int(radius)
            radius_val = max(radius_val, 1)
            radius_val = min(radius_val, 10)
        except:
            radius_val = 2

        cache_token = self.get_hash([ entity, str(radius_val) ], prefix="hood-")
        handle, html_path = tempfile.mkstemp(suffix=".html", prefix="rc_hood", dir="/tmp")

        subgraph = self.net.get_subgraph(search_term=entity, radius=radius_val)
        hood = self.net.extract_neighborhood(subgraph, entity, html_path)

        with open(html_path, "r") as f:
            html = f.read()
            self.disk_cache[cache_token] = html
    
        os.remove(html_path)

        response = hood.serialize(t0, cache_token)
        status = HTTPStatus.OK.value

        return response, status


    def fetch_graph (self, cache_token):
        """
        fetch the HTML to render the graph diagram referenced by the
        `cache_token` parameter
        """
        if cache_token in self.disk_cache:
            html = self.disk_cache[cache_token]
            response = render_template_string(html)
            status = HTTPStatus.OK.value
        else:
            response = f"<strong>NOT FOUND: {cache_token}</strong>"
            status = HTTPStatus.BAD_REQUEST.value

        return response, status


    def get_entity_links (self, index):
        """
        render HTML for the link viewer for the entity referenced by
        `index`
        """
        html = None
        status = HTTPStatus.BAD_REQUEST.value

        try:
            id = int(index)
        except:
            id = -1

        if id >= 0 and id < len(self.net.id_list):
            uuid = self.net.id_list[id]

            if uuid in self.links:
                html = self.links[uuid]
                status = HTTPStatus.OK.value

        return html, status


APP = RCServerApp(__name__)
CACHE = Cache(APP, config={"CACHE_TYPE": "simple"})


######################################################################
## page routes

@APP.route("/index.html")
@APP.route("/home/")
def home_redirects ():
    return redirect(url_for("home_page"))

@APP.route("/")
def home_page ():
    query = APP.extract_query_home(request)
    return render_template("index.html", query=query)


@APP.route("/feedback")
@APP.route("/feedback/")
@APP.route("/feedback.html")
@APP.route("/hitl.html")
@APP.route("/hitl")
def hitl_redirect ():
    return redirect(url_for("hitl_page"))

@APP.route("/hitl/")
def hitl_page ():
    return render_template("hitl.html")


@APP.route("/research")
@APP.route("/research.html")
@APP.route("/workbench")
@APP.route("/workbench.html")
@APP.route("/work")
@APP.route("/work.html")
def work_redirect ():
    return redirect(url_for("work_page"))

@APP.route("/work/")
def work_page ():
    return render_template("work.html")


## CSS, JavaScript, etc.
@APP.route("/css/pure-min.css")
@APP.route("/css/grids-responsive-min.css")
## plus other well-known routes
@APP.route("/favicon.png")
@APP.route("/apple-touch-icon.png")
def static_from_root ():
    return send_from_directory(APP.static_folder, request.path[1:])


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
            "url": "https://github.com/Coleridge-Initiative/RCServer"
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
    response, status = APP.run_entity_query(radius, entity)
    return response, status


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
      '400':
        description: bad request; is the `index` parameter valid?
    """
    html, status = APP.get_entity_links(index)
    return jsonify(html), status


@CACHE.cached(timeout=3000)
@APP.route("/api/v1/post-example", methods=["POST"])
def api_post_example ():
    """
    example to POST some stuff
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
    
    view = {
        "received": mcguffin
        }

    status = HTTPStatus.OK.value

    return jsonify(view), status


@CACHE.cached(timeout=3000)
@APP.route("/graph/<cache_token>", methods=["GET"])
def fetch_graph_html (cache_token):
    """
    fetch the HTML to render a cached network diagram 
    """
    response, status = APP.fetch_graph(cache_token)
    return response, status


######################################################################
## main

def main (args):
    """
    dev/test entry point
    """
    if args.token:
        expiry = datetime.timedelta(days=APP.DEFAULT_EXPIRY)
        scope = copy.deepcopy(APP.AGENCY_SCOPE)
        scope["id"] = args.token

        # generate web token
        token = APP.jwt_encode(APP.config["SECRET_KEY"], expiry, scope)
        print(token)

        # confirm web token
        payload = APP.jwt_decode(APP.config["SECRET_KEY"], token)
        print(payload)

    elif args.pre:
        # pre-compute the links
        print(f"pre-computing links with: {args.corpus}")

    else:
        # run the app
        APP.corpus_path = Path(args.corpus)
        APP.run(host="0.0.0.0", port=args.port, debug=True)


if __name__ == "__main__":
    # parse the command line arguments, if any
    parser = argparse.ArgumentParser(
        description="Rich Context: server, web app, API, UI"
        )

    parser.add_argument(
        "--port",
        type=int,
        default=APP.DEFAULT_PORT,
        help="web IP port"
        )

    parser.add_argument(
        "--corpus",
        type=str,
        default=APP.DEFAULT_CORPUS,
        help="corpus file as JSON-LD"
        )

    parser.add_argument(
        "--pre",
        type=bool,
        default=APP.DEFAULT_PRECOMPUTE,
        help="pre-compute links with the corpus file"
        )

    parser.add_argument(
        "--token",
        type=str,
        default=APP.DEFAULT_TOKEN,
        help="generate a web token for agency staff"
        )

    main(parser.parse_args())
