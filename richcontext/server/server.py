#!/usr/bin/env python
# encoding: utf-8

from operator import itemgetter
from pathlib import Path
from pyvis.network import Network
from scipy.stats import percentileofscore
import codecs
import json
import networkx as nx
import numpy as np
import pandas as pd

import sys
import time
import traceback


class RCNeighbors:
    def __init__ (self):
        self.prov = []
        self.data = []
        self.auth = []
        self.jour = []
        self.pubs = []


    def serialize (self, t0, cache_token):
        """
        serialize this subgraph/neighborhood as JSON
        """
        view = {
            "prov": sorted(self.prov, reverse=True),
            "data": sorted(self.data, reverse=True),
            "pubs": sorted(self.pubs, reverse=True),
            "auth": sorted(self.auth, reverse=True),
            "jour": sorted(self.jour, reverse=True),
            "toke": cache_token,
            "time": "{:.2f}".format((time.time() - t0) * 1000.0)
            }

        return json.dumps(view, indent=4, sort_keys=True, ensure_ascii=False)


class RCNetwork:
    MAX_TITLE_LEN = 40

    def __init__ (self):
        self.id_list = []
        self.labels = {}

        self.nxg = None
        self.scale = {}

        self.providers = {}
        self.datasets = {}
        self.journals = {}
        self.authors = {}
        self.publications = {}


    def get_id (self, id):
        """
        lookup the numeric ID for an element
        """
        return int(self.id_list.index(id))


    def parse_metadata (self, elem):
        """
        parse the required metadata items from one element in the graph
        """
        kind = elem["@type"]
        title = elem["dct:title"]["@value"]
        id = elem["@id"].split("#")[1]

        self.id_list.append(id)
        self.labels[self.get_id(id)] = title

        return id, kind, title, elem


    def parse_corpus (self, path):
        """
        parse each of the entities within the KG
        """
        with codecs.open(path, "r", encoding="utf8") as f:
            jld_corpus = json.load(f)
            corpus = jld_corpus["@graph"]

        entities = [ self.parse_metadata(e) for e in corpus ]

        # providers
        for id, kind, title, elem in entities:
            if kind == "Provider":
                if "dct:identifier" in elem:
                    ror = elem["dct:identifier"]["@value"]
                else:
                    ror = ""

                view = {
                    "id": id,
                    "title": title,
                    "ror": ror
                    }

                self.providers[id] = view

        # datasets
        for id, kind, title, elem in entities:
            if kind == "Dataset":
                prov_id = elem["dct:publisher"]["@value"]

                view = {
                    "id": id,
                    "title": title,
                    "provider": prov_id
                    }

                self.datasets[id] = view

        # journals
        for id, kind, title, elem in entities:
            if kind == "Journal":
                if "dct:identifier" in elem:
                    issn = elem["dct:identifier"]["@value"]
                else:
                    issn = ""

                view = {
                    "id": id,
                    "title": title,
                    "issn": issn
                    }

                self.journals[id] = view

        # authors
        for id, kind, title, elem in entities:
            if kind == "Author":
                if "dct:identifier" in elem:
                    orcid = elem["dct:identifier"]["@value"]
                else:
                    orcid = ""

                view = {
                    "id": id,
                    "title": title,
                    "orcid": orcid
                    }

                self.authors[id] = view

        # publications
        for id, kind, title, elem in entities:
            if kind == "ResearchPublication":
                # link the datasets
                data_list = []
                l = elem["cito:citesAsDataSource"]

                if isinstance(l, dict):
                    l = [l]
            
                for d in l:
                    data_id = d["@id"].split("#")[1]
                    self.datasets[data_id]["used"] = True
                    data_list.append(data_id)

                    prov_id = self.datasets[data_id]["provider"]
                    self.providers[prov_id]["used"] = True

                # link the authors
                auth_list = []
        
                if "dct:creator" in elem:
                    l = elem["dct:creator"]
                else:
                    l = []

                if isinstance(l, dict):
                    l = [l]

                for a in l:
                    auth_id = a["@id"].split("#")[1]
                    self.authors[auth_id]["used"] = True
                    auth_list.append(auth_id)

                # add DOI
                if "dct:identifier" in elem:
                    doi = elem["dct:identifier"]["@value"]
                else:
                    doi = ""

                if "dct:publisher" in elem:
                    jour_id = elem["dct:publisher"]["@id"].split("#")[1]
                    self.journals[jour_id]["used"] = True

                view = {
                    "id": id,
                    "title": title,
                    "doi": doi,
                    "journal": jour_id,
                    "datasets": data_list,
                    "authors": auth_list
                    }

                self.publications[id] = view


    def build_analytics_graph (self):
        """
        build a graph to calculate analytics
        """
        self.nxg = nx.Graph()

        for p in self.providers.values():
            if "used" in p:
                self.nxg.add_node(self.get_id(p["id"]))

        for d in self.datasets.values():
            if "used" in d:
                self.nxg.add_node(self.get_id(d["id"]))
                self.nxg.add_edge(self.get_id(d["id"]), self.get_id(d["provider"]))

        for a in self.authors.values():
            if "used" in a:
                self.nxg.add_node(self.get_id(a["id"]))

        for j in self.journals.values():
            if "used" in j:
                self.nxg.add_node(self.get_id(j["id"]))

        for p in self.publications.values():
            self.nxg.add_node(self.get_id(p["id"]))

            if p["journal"]:
                self.nxg.add_edge(self.get_id(p["id"]), self.get_id(p["journal"]))

            for d in p["datasets"]:
                self.nxg.add_edge(self.get_id(p["id"]), self.get_id(d))

            for a in p["authors"]:
                self.nxg.add_edge(self.get_id(p["id"]), self.get_id(a))


    @classmethod
    def calc_quantiles (cls, metrics, num_q):
        """
        calculate quantiles for the given list of metrics
        """
        bins = np.linspace(0, 1, num=num_q, endpoint=True)
        s = pd.Series(metrics)
        q = s.quantile(bins, interpolation="nearest")

        try:
            dig = np.digitize(metrics, q) - 1
        except ValueError as e:
            print("ValueError:", str(e), metrics, s, q, bins)
            sys.exit(-1)

        quantiles = []

        for idx, q_hi in q.iteritems():
            quantiles.append(q_hi)

        return quantiles


    def scale_ranks (self, scale_factor=3):
        """
        run quantile analysis on centrality metrics, to assess the
        relative impact of each element in the KG
        """
        result = nx.pagerank(self.nxg)
        ranks = list(result.values())

        quant = self.calc_quantiles(ranks, num_q=10)
        num_quant = len(quant)

        for id, rank in sorted(result.items(), key=itemgetter(1), reverse=True):
            impact = percentileofscore(ranks, rank)
            scale = (((impact / num_quant) + 5) * scale_factor)
            self.scale[id] = [int(round(scale)), impact / 100.0]


    def load_network (self, path):
        """
        full usage pattern, prior to subgraph
        """
        t0 = time.time()

        self.parse_corpus(path)
        self.build_analytics_graph()
        self.scale_ranks()

        elapsed_time = (time.time() - t0) * 1000.0
        return elapsed_time


    def get_subgraph (self, search_term, radius):
        """
        use BFS to label nodes as part of a 'neighborhood' subgraph
        """
        subgraph = set([])

        for node_id, label in self.labels.items():
            if label == search_term:
                r = nx.bfs_edges(self.nxg, source=node_id, depth_limit=radius)
                subgraph = set([node_id])

                for _, neighbor in r:
                    subgraph.add(neighbor)

        return subgraph


    def extract_neighborhood (self, subgraph, search_term, html_path):
        """
        extract the neighbor entities from the subgraph, while
        generating a network diagram
        """
        hood = RCNeighbors()
        g = Network(notebook=False, height="450px", width="100%")
        g.force_atlas_2based()

        for p in self.providers.values():
            if "used" in p:
                p_id = self.get_id(p["id"])
        
                if p_id in subgraph:
                    scale, impact = self.scale[p_id]
                    hood.prov.append([ p_id, "{:.4f}".format(impact), p["title"], p["ror"] ])

                    title = "{}<br/>rank: {:.4f}<br/>{}".format(p["title"], impact, p["ror"])
                    g.add_node(p_id, label=p["title"], title=title, color="orange", size=scale)

        for d in self.datasets.values():
            if "used" in d:
                d_id = self.get_id(d["id"])
        
                if d_id in subgraph:
                    p_id = self.get_id(d["provider"])
                    scale, impact = self.scale[d_id]
                    hood.data.append([ d_id, "{:.4f}".format(impact), d["title"], self.labels[p_id] ])

                    title = "{}<br/>rank: {:.4f}<br/>provider: {}".format(d["title"], impact, self.labels[p_id])
                    g.add_node(d_id, label=d["title"], title=title, color="red", size=scale)

                    if p_id in subgraph:
                        g.add_edge(d_id, p_id, color="gray")

        for a in self.authors.values():
            if "used" in a:
                a_id = self.get_id(a["id"])

                if a_id in subgraph:
                    scale, impact = self.scale[a_id]
                    hood.auth.append([ a_id, "{:.4f}".format(impact), a["title"], a["orcid"] ])

                    title = "{}<br/>rank: {:.4f}<br/>{}".format(a["title"], impact, a["orcid"])
                    g.add_node(a_id, label=a["title"], title=title, color="purple", size=scale)

        for j in self.journals.values():
            if "used" in j:
                j_id = self.get_id(j["id"])

                if j_id in subgraph and not j["title"] == "unknown":
                    scale, impact = self.scale[j_id]
                    hood.jour.append([ j_id, "{:.4f}".format(impact), j["title"], j["issn"] ])

                    title = "{}<br/>rank: {:.4f}<br/>{}".format(j["title"], impact, j["issn"])
                    g.add_node(j_id, label=j["title"], title=title, color="green", size=scale)

        for p in self.publications.values():
            p_id = self.get_id(p["id"])

            if p_id in subgraph:
                if len(p["title"]) >= self.MAX_TITLE_LEN:
                    abbrev_title = p["title"][:self.MAX_TITLE_LEN] + "..."
                else:
                    abbrev_title = p["title"]

                scale, impact = self.scale[p_id]
                hood.pubs.append([ p_id, "{:.4f}".format(impact), abbrev_title, p["doi"] ])

                title = "{}<br/>rank: {:.4f}<br/>{}".format(p["title"], impact, p["doi"])
                g.add_node(p_id, label=p["title"], title=title, color="blue", size=scale)

                if p["journal"]:
                    j_id = self.get_id(p["journal"])

                    if j_id in subgraph:
                        g.add_edge(p_id, j_id, color="gray")

                for d in p["datasets"]:
                    d_id = self.get_id(d)
            
                    if d_id in subgraph:
                        g.add_edge(p_id, d_id, color="gray")

                for a in p["authors"]:
                    a_id = self.get_id(a)
            
                    if a_id in subgraph:
                        g.add_edge(p_id, a_id, color="gray")

        #g.show_buttons()
        g.write_html(html_path, notebook=False)

        return hood


######################################################################

def main ():
    # build a graph from the JSON-LD corpus
    net = RCNetwork()
    net.parse_corpus(Path("tmp.jsonld"))

    # rank and scale each entity
    net.build_analytics_graph()
    net.scale_ranks()

    # constrain the graph
    t0 = time.time()

    search_term = "IRI Infoscan"
    radius = 2

    subgraph = net.get_subgraph(search_term=search_term, radius=radius)
    hood = net.extract_neighborhood(subgraph, search_term, "corpus.html")

    print(hood.serialize(t0))


if __name__ == "__main__":
    main()
