#!/usr/bin/env python
# encoding: utf-8

from collections import defaultdict
from css_html_js_minify import html_minify
from functools import lru_cache
from jinja2 import Environment, FileSystemLoader
from operator import itemgetter
from pathlib import Path
from pyvis.network import Network
import codecs
import json
import networkx as nx
import numpy as np
import pandas as pd
import scipy.stats as stats
import sys
import time
import traceback


class RCNeighbors:
    def __init__ (self):
        self.prov = []
        self.data = []
        self.publ = []
        self.jour = []
        self.auth = []
        self.topi = []


    def serialize (self, t0, cache_token):
        """
        serialize this subgraph/neighborhood as JSON
        """
        view = {
            "prov": sorted(self.prov, key=lambda x: x[1], reverse=True),
            "data": sorted(self.data, key=lambda x: x[1], reverse=True),
            "publ": sorted(self.publ, key=lambda x: x[1], reverse=True),
            "jour": sorted(self.jour, key=lambda x: x[1], reverse=True),
            "auth": sorted(self.auth, key=lambda x: x[1], reverse=True),
            "topi": sorted(self.topi, key=lambda x: x[1], reverse=True),
            "toke": cache_token,
            "time": "{:.2f}".format((time.time() - t0) * 1000.0)
            }

        return json.dumps(view, indent=4, sort_keys=True, ensure_ascii=False)


class RCNetworkNode:
    def __init__ (self, view=None, elem=None):
        self.view = view
        self.elem = elem


class RCNetwork:
    MAX_TITLE_LEN = 100
    Z_975 = stats.norm.ppf(q=0.975)

    def __init__ (self):
        self.id_list = []
        self.labels = {}

        self.nxg = None
        self.scale = {}

        self.prov = {}
        self.data = {}
        self.publ = {}
        self.jour = {}
        self.auth = {}
        self.topi = {}


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
        unknown_journal = None

        # providers
        for id, kind, title, elem in entities:
            if kind == "Provider":
                if "dct:identifier" in elem:
                    ror = elem["dct:identifier"]["@value"]
                else:
                    ror = ""

                self.prov[id] = RCNetworkNode(
                    view={
                        "id": id,
                        "title": title,
                        "ror": ror
                        },
                    elem=elem
                    )

        # datasets
        for id, kind, title, elem in entities:
            if kind == "Dataset":
                prov_id = elem["dct:publisher"]["@value"]

                # url, if any
                if "foaf:page" in elem:
                    url = elem["foaf:page"]["@value"]
                else:
                    url = None

                self.data[id] = RCNetworkNode(
                    view={
                        "id": id,
                        "title": title,
                        "provider": prov_id,
                        "url": url
                        },
                    elem=elem
                    )

        # journals
        for id, kind, title, elem in entities:
            if kind == "Journal":
                if title == "unknown":
                    unknown_journal = id

                else:
                    if "dct:identifier" in elem:
                        issn = elem["dct:identifier"]["@value"]
                    else:
                        issn = ""

                    # url, if any
                    if "foaf:page" in elem:
                        url = elem["foaf:page"]["@value"]
                    else:
                        url = None

                    self.jour[id] = RCNetworkNode(
                        view={
                            "id": id,
                            "title": title,
                            "issn": issn,
                            "url": url
                            },
                        elem=elem
                        )

        # authors
        for id, kind, title, elem in entities:
            if kind == "Author":
                if "dct:identifier" in elem:
                    orcid = elem["dct:identifier"]["@value"]
                else:
                    orcid = ""

                self.auth[id] = RCNetworkNode(
                    view={
                        "id": id,
                        "title": title,
                        "orcid": orcid
                        },
                    elem=elem
                    )

        # topics
        for id, kind, title, elem in entities:
            if kind == "Topic":
                self.topi[id] = RCNetworkNode(
                    view={
                        "id": id,
                        "title": title
                        },
                    elem=elem
                    )

        # publications
        for id, kind, title, elem in entities:
            if kind == "ResearchPublication":
                # link the datasets
                data_list = []
                l = elem["cito:citesAsDataSource"]

                # if there's only one element, JSON-LD will link
                # directly rather than enclose within a list
                if isinstance(l, dict):
                    l = [l]
            
                for d in l:
                    data_id = d["@id"].split("#")[1]
                    self.data[data_id].view["used"] = True
                    data_list.append(data_id)

                    prov_id = self.data[data_id].view["provider"]
                    self.prov[prov_id].view["used"] = True

                # link the authors
                auth_list = []
        
                if "dct:creator" in elem:
                    l = elem["dct:creator"]
                else:
                    l = []

                # ibid.
                if isinstance(l, dict):
                    l = [l]

                for a in l:
                    auth_id = a["@id"].split("#")[1]
                    self.auth[auth_id].view["used"] = True
                    auth_list.append(auth_id)

                # link the topics
                topi_list = []

                if "dct:subject" in elem:
                    l = elem["dct:subject"]
                else:
                    l = []

                # ibid.
                if isinstance(l, dict):
                    l = [l]

                for t in l:
                    topi_id = t["@id"].split("#")[1]
                    self.topi[topi_id].view["used"] = True
                    topi_list.append(topi_id)

                # add DOI
                if "dct:identifier" in elem:
                    doi = elem["dct:identifier"]["@value"]
                else:
                    doi = ""

                # add journal
                if "dct:publisher" in elem:
                    jour_id = elem["dct:publisher"]["@id"].split("#")[1]

                    if jour_id == unknown_journal:
                        jour_id = None
                    else:
                        self.jour[jour_id].view["used"] = True

                # add abstract
                if "cito:description" in elem:
                    abstract = elem["cito:description"]["@value"]
                else:
                    abstract = ""

                # open access PDF, if any
                if "openAccess" in elem:
                    pdf = elem["openAccess"]["@value"]
                else:
                    pdf = None

                self.publ[id] = RCNetworkNode(
                    view={
                        "id": id,
                        "title": title,
                        "doi": doi,
                        "pdf": pdf,
                        "journal": jour_id,
                        "abstract": abstract,
                        "datasets": data_list,
                        "authors": auth_list,
                        "topics": topi_list
                        },
                    elem=elem
                    )


    ######################################################################
    ## graph analytics

    @classmethod
    @lru_cache()
    def point_estimate (cls, x, n):
        return (float(x) + cls.Z_975) / (float(n) + 2.0 * cls.Z_975)


    def propagate_pdf (self, entity_class, entity_kind):
        """
        propagate probability distribution functions across the graph,
        for conditional probabilities related to datasets
        """
        trials = defaultdict(int)
        counts = defaultdict(dict)

        for p in self.publ.values():
            if p.view[entity_kind]:
                coll = p.view[entity_kind]

                if isinstance(coll, str):
                    coll = [coll]

                for e in coll:
                    n = float(len(p.view["datasets"]))
                    trials[e] += n

                    for d in p.view["datasets"]:
                        if d not in counts[e]:
                            counts[e][d] = 1
                        else:
                            counts[e][d] += 1

        for e in entity_class.values():
            e_id = e.view["id"]
            mle = {}

            for d, x in counts[e_id].items():
                pt_est = self.point_estimate(x, trials[e_id])
                mle[self.get_id(d)] = [x, pt_est]

            e.view["mle"] = mle


    def build_analytics_graph (self):
        """
        build a graph to calculate analytics
        """
        self.nxg = nx.Graph()

        for p in self.prov.values():
            if "used" in p.view:
                self.nxg.add_node(self.get_id(p.view["id"]))

        for d in self.data.values():
            if "used" in d.view:
                self.nxg.add_node(self.get_id(d.view["id"]))
                self.nxg.add_edge(self.get_id(d.view["id"]), self.get_id(d.view["provider"]), weight=10.0)

        for a in self.auth.values():
            if "used" in a.view:
                self.nxg.add_node(self.get_id(a.view["id"]))

        for j in self.jour.values():
            if "used" in j.view:
                self.nxg.add_node(self.get_id(j.view["id"]))

        for t in self.topi.values():
            if "used" in t.view:
                self.nxg.add_node(self.get_id(t.view["id"]))

        for p in self.publ.values():
            self.nxg.add_node(self.get_id(p.view["id"]))

            if p.view["journal"]:
                self.nxg.add_edge(self.get_id(p.view["id"]), self.get_id(p.view["journal"]), weight=1.0)

            for d in p.view["datasets"]:
                self.nxg.add_edge(self.get_id(p.view["id"]), self.get_id(d), weight=20.0)

            for a in p.view["authors"]:
                self.nxg.add_edge(self.get_id(p.view["id"]), self.get_id(a), weight=20.0)

            for t in p.view["topics"]:
                self.nxg.add_edge(self.get_id(p.view["id"]), self.get_id(t), weight=10.0)


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
        run quantile analysis on centrality metrics, assessing the
        relative impact of each element in the KG
        """
        result = nx.eigenvector_centrality_numpy(self.nxg, weight="weight")
        ranks = list(result.values())

        quant = self.calc_quantiles(ranks, num_q=10)
        num_quant = len(quant)

        for id, rank in sorted(result.items(), key=itemgetter(1), reverse=True):
            impact = stats.percentileofscore(ranks, rank)
            scale = (((impact / num_quant) + 5) * scale_factor)
            self.scale[id] = [int(round(scale)), impact / 100.0]


    def load_network (self, path):
        """
        run the full usage pattern, prior to use of serialize() or
        subgraph()
        """
        t0 = time.time()

        self.parse_corpus(path)

        self.propagate_pdf(self.auth, "authors")
        self.propagate_pdf(self.jour, "journal")
        self.propagate_pdf(self.topi, "topics")

        self.build_analytics_graph()
        self.scale_ranks()

        elapsed_time = (time.time() - t0) * 1000.0
        return elapsed_time


    ######################################################################
    ## ser/de for pre-computing, then later a fast load/launch

    def serialize (self, links, path=Path("precomp.json")):
        """
        serialize all of the data structures required to recreate the
        knowledge graph
        """
        g = nx.readwrite.json_graph.node_link_data(self.nxg),

        view = [
            g,
            links,

            self.id_list,
            list(self.labels.items()),
            list(self.scale.items()),

            [ p.view for p in self.prov.values() ],
            [ d.view for d in self.data.values() ],
            [ p.view for p in self.publ.values() ],
            [ j.view for j in self.jour.values() ],
            [ a.view for a in self.auth.values() ],
            [ t.view for t in self.topi.values() ]
            ]

        with codecs.open(path, "wb", encoding="utf8") as f:
            json.dump(view, f, ensure_ascii=False)


    def deserialize (self, path=Path("precomp.json")):
        """
        deserialize all of the data structures required to recreate
        the knowledge graph
        """
        with codecs.open(path, "r", encoding="utf8") as f:
            view = json.load(f)
            g, links, id_list, labels, scale, prov, data, publ, jour, auth, topi = view

            # deserialize the graph metadata
            self.nxg = nx.readwrite.json_graph.node_link_graph(g[0])
            self.id_list = id_list

            for k, v in labels:
                self.labels[k] = v

            for k, v in scale:
                self.scale[k] = v

            # deserialize each dimension of entities in the KG
            for view in prov:
                self.prov[view["id"]] = RCNetworkNode(view=view)

            for view in data:
                self.data[view["id"]] = RCNetworkNode(view=view)

            for view in publ:
                self.publ[view["id"]] = RCNetworkNode(view=view)

            for view in jour:
                self.jour[view["id"]] = RCNetworkNode(view=view)

            for view in auth:
                self.auth[view["id"]] = RCNetworkNode(view=view)

            for view in topi:
                self.topi[view["id"]] = RCNetworkNode(view=view)

            return links


    ######################################################################
    ## linked data viewer

    @classmethod
    def get_template (cls, template_folder, template_path):
        """
        load a Jinja2 template
        """
        return Environment(loader=FileSystemLoader(template_folder)).get_template(template_path)


    @classmethod
    def render_template (cls, template, **kwargs):
        return html_minify(template.render(kwargs)).replace("  ", " ").replace("> <", "><").replace(" >", ">")


    def setup_render (self, template_folder):
        self.data_template = self.get_template(template_folder, "links/data.html")
        self.prov_template = self.get_template(template_folder, "links/prov.html")
        self.publ_template = self.get_template(template_folder, "links/publ.html")
        self.jour_template = self.get_template(template_folder, "links/jour.html")
        self.auth_template = self.get_template(template_folder, "links/auth.html")
        self.topi_template = self.get_template(template_folder, "links/topi.html")


    def calc_rank (self, rerank, neighbor, e):
        """
        calculate a distance metric to the selected dataset 
        """
        neighbor_scale, neighbor_impact = self.scale[neighbor]
        rank = (0, 0, 0.0, neighbor_impact)

        if rerank:
            p = self.publ[self.id_list[neighbor]]

            if "rank" in p.view:
                rank = p.view["rank"]
            else:
                if rerank in e.view["mle"]:
                    count, pt_est = e.view["mle"][rerank]
                else:
                    count = 0
                    pt_est = 0.0

                rank = (0, count, pt_est, neighbor_impact)

        return rank


    def reco_prov (self, p):
        """
        recommend ordered links to this provider entity
        """
        uuid = None
        title = None
        rank = None
        url = None
        ror = None
        data_list = None

        p_id = self.get_id(p.view["id"])

        if p_id in self.scale:
            scale, impact = self.scale[p_id]
            edges = self.nxg[self.get_id(p.view["id"])]
            data_list = []

            for neighbor, attr in edges.items():
                neighbor_scale, neighbor_impact = self.scale[neighbor]
                data_list.append([ neighbor, self.labels[neighbor], neighbor_impact ])

            if len(p.view["ror"]) < 1:
                ror = None
                url = None
            else:
                ror = p.view["ror"].replace("https://ror.org/", "")
                url = p.view["ror"]

            uuid = p.view["id"]
            title = p.view["title"]
            rank = "{:.4f}".format(impact)
            data_list = sorted(data_list, key=lambda x: x[2], reverse=True)

        return uuid, title, rank, url, ror, data_list


    def render_prov (self, p):
        """
        render HTML for a provider
        """
        html = None
        uuid, title, rank, url, ror, data_list = self.reco_prov(p)

        if uuid:
            html = self.render_template(
                self.prov_template, 
                uuid=uuid,
                title=title,
                rank=rank,
                url=url,
                ror=ror,
                data_list=data_list
                )

        return html


    def reco_data (self, d):
        """
        recommend ordered links to this dataset entity
        """
        uuid = None
        title = None
        rank = None
        url = None
        provider = None
        publ_list = []

        d_id = self.get_id(d.view["id"])

        if d_id in self.scale:
            scale, impact = self.scale[d_id]
            edges = self.nxg[self.get_id(d.view["id"])]
            publ_list = []

            p_id = self.get_id(d.view["provider"])
            seen_set = set([ p_id ])

            for neighbor, attr in edges.items():
                if neighbor not in seen_set:
                    neighbor_scale, neighbor_impact = self.scale[neighbor]
                    publ_list.append([ neighbor, self.labels[neighbor], neighbor_impact ])

            uuid = d.view["id"]
            title = d.view["title"]
            rank = "{:.4f}".format(impact)
            url = d.view["url"]
            provider = [p_id, self.labels[p_id]]
            publ_list = sorted(publ_list, key=lambda x: x[2], reverse=True)

        return uuid, title, rank, url, provider, publ_list


    def render_data (self, d):
        """
        render HTML for a dataset
        """
        html = None
        uuid, title, rank, url, provider, publ_list = self.reco_data(d)

        if uuid:
            html = self.render_template(
                self.data_template, 
                uuid=uuid,
                title=title,
                rank=rank,
                url=url,
                provider=provider,
                publ_list=publ_list
                )

        return html


    def reco_auth (self, a, rerank):
        """
        recommend ordered links to this author entity
        """
        uuid = None
        title = None
        rank = None
        url = None
        orcid = None
        publ_list = None

        a_id = self.get_id(a.view["id"])

        if a_id in self.scale:
            scale, impact = self.scale[a_id]
            edges = self.nxg[self.get_id(a.view["id"])]
            publ_list = []

            for neighbor, attr in edges.items():
                rank = self.calc_rank(rerank, neighbor, a)
                publ_list.append([ neighbor, self.labels[neighbor], rank ])

            if len(a.view["orcid"]) < 1:
                orcid = None
                url = None
            else:
                orcid = a.view["orcid"].replace("https://orcid.org/", "")
                url = a.view["orcid"]

            uuid = a.view["id"]
            title = a.view["title"]
            rank = "{:.4f}".format(impact)
            publ_list = sorted(publ_list, key=lambda x: x[2], reverse=True)

        return uuid, title, rank, url, orcid, publ_list


    def render_auth (self, a, rerank=False):
        """
        render HTML for an author
        """
        html = None
        uuid, title, rank, url, orcid, publ_list = self.reco_auth(a, rerank)

        if uuid:
            html = self.render_template(
                self.auth_template, 
                uuid=uuid,
                title=title,
                rank=rank,
                url=url,
                orcid=orcid,
                publ_list=publ_list
                )

        return html


    def reco_jour (self, j):
        """
        recommend ordered links to this journal entity
        """
        uuid = None
        title = None
        rank = None
        url = None
        issn = None
        publ_list = None

        j_id = self.get_id(j.view["id"])

        if j_id in self.scale:
            scale, impact = self.scale[j_id]
            edges = self.nxg[self.get_id(j.view["id"])]
            publ_list = []

            for neighbor, attr in edges.items():
                neighbor_scale, neighbor_impact = self.scale[neighbor]
                publ_list.append([ neighbor, self.labels[neighbor], neighbor_scale ])

            if len(j.view["issn"]) < 1:
                issn = None
            else:
                issn = j.view["issn"].replace("https://portal.issn.org/resource/ISSN/", "")

            if j.view["url"]:
                url = j.view["url"]
            elif issn:
                url = issn
            else:
                url = None

            uuid = j.view["id"]
            title = j.view["title"]
            rank = "{:.4f}".format(impact)
            publ_list = sorted(publ_list, key=lambda x: x[2], reverse=True)

        return uuid, title, rank, url, issn, publ_list


    def render_jour (self, j):
        """
        render HTML for a journal
        """
        html = None
        uuid, title, rank, url, issn, publ_list = self.reco_jour(j)

        if uuid:
            html = self.render_template(
                self.jour_template, 
                uuid=uuid,
                title=title,
                rank=rank,
                url=url,
                issn=issn,
                publ_list=publ_list
                )

        return html


    def reco_topi (self, t):
        """
        recommend ordered links to this topic entity
        """
        uuid = None
        title = None
        rank = None
        publ_list = None

        t_id = self.get_id(t.view["id"])

        if t_id in self.scale:
            scale, impact = self.scale[t_id]
            edges = self.nxg[self.get_id(t.view["id"])]
            publ_list = []

            for neighbor, attr in edges.items():
                neighbor_scale, neighbor_impact = self.scale[neighbor]
                publ_list.append([ neighbor, self.labels[neighbor], neighbor_scale ])

            uuid = t.view["id"]
            title = t.view["title"]
            rank = "{:.4f}".format(impact)
            publ_list = sorted(publ_list, key=lambda x: x[2], reverse=True)

        return uuid, title, rank, publ_list


    def render_topi (self, t):
        """
        render HTML for a topic
        """
        html = None
        uuid, title, rank, publ_list = self.reco_topi(t)

        if uuid:
            html = self.render_template(
                self.topi_template, 
                uuid=uuid,
                title=title,
                rank=rank,
                publ_list=publ_list
                )

        return html


    def reco_publ (self, p):
        """
        recommend ordered links to this publication entity
        """
        uuid = None
        title = None
        rank = None
        url = None
        doi = None
        pdf = None
        journal = None
        abstract = None
        auth_list = None
        data_list = None
        topi_list = None

        p_id = self.get_id(p.view["id"])

        if p_id in self.scale:
            scale, impact = self.scale[p_id]
            journal = None

            if p.view["journal"]:
                j_id = self.get_id(p.view["journal"])

                if self.labels[j_id] != "unknown":
                    journal = [ j_id, self.labels[j_id] ]

            auth_list = []

            for a in p.view["authors"]:
                a_id = self.get_id(a)
                # do not sort; preserve the author order
                auth_list.append([ a_id, self.labels[a_id] ])

            data_list = []

            for d in p.view["datasets"]:
                d_id = self.get_id(d)
                neighbor_scale, neighbor_impact = self.scale[d_id]
                data_list.append([ d_id, self.labels[d_id], neighbor_scale ])

            topi_list = []

            for t in p.view["topics"]:
                t_id = self.get_id(t)
                neighbor_scale, neighbor_impact = self.scale[t_id]
                topi_list.append([ t_id, self.labels[t_id], neighbor_scale ])

            if len(p.view["doi"]) < 1:
                url = None
                doi = None
            else:
                url = p.view["doi"]
                doi = p.view["doi"].replace("https://doi.org/", "")

            if "abstract" not in p.view or len(p.view["abstract"]) < 1:
                abstract = None
            else:
                abstract = p.view["abstract"]

            uuid = p.view["id"]
            title = p.view["title"]
            rank = "{:.4f}".format(impact)
            pdf = p.view["pdf"]
            data_list = sorted(data_list, key=lambda x: x[2], reverse=True)
            topi_list = sorted(topi_list, key=lambda x: x[2], reverse=True)

        return uuid, title, rank, url, doi, pdf, journal, abstract, auth_list, data_list, topi_list


    def render_publ (self, p):
        """
        render HTML for a publication
        """
        html = None
        uuid, title, rank, url, doi, pdf, journal, abstract, auth_list, data_list, topi_list = self.reco_publ(p)

        if uuid:
            html = self.render_template(
                self.publ_template, 
                uuid=uuid,
                title=title,
                rank=rank,
                url=url,
                doi=doi,
                pdf=pdf,
                journal=journal,
                abstract=abstract,
                auth_list=auth_list,
                data_list=data_list,
                topi_list=topi_list
                )

        return html


    def remap_list (self, l):
        """
        remap the networkx graph index values to UUIDs
        """
        return [ [self.id_list[x[0]], x[1]] for x in l ]


    def lookup_entity (self, uuid):
        """
        get recommended links for the given entity
        """
        response = None

        if uuid in self.prov:
            uuid, title, rank, url, ror, data_list = self.reco_prov(self.prov[uuid])

            response = {
                "title": title,
                "rank": rank,
                "url": url,
                "ror": ror,
                "data": self.remap_list(data_list)
                }

        elif uuid in self.data:
            uuid, title, rank, url, provider, publ_list = self.reco_data(self.data[uuid])

            response = {
                "title": title,
                "rank": rank,
                "url": url,
                "prov": [ self.id_list[provider[0]], provider[1] ],
                "publ": self.remap_list(publ_list)
                }

        elif uuid in self.publ:
            uuid, title, rank, url, doi, pdf, journal, abstract, auth_list, data_list, topi_list = self.reco_publ(self.publ[uuid])

            response = {
                "title": title,
                "rank": rank,
                "url": url,
                "doi": doi,
                "pdf": pdf,
                "abstract": abstract,
                "jour": [ self.id_list[journal[0]], journal[1] ],
                "auth": self.remap_list(auth_list),
                "data": self.remap_list(data_list),
                "topi": self.remap_list(topi_list)
                }

        elif uuid in self.auth:
            uuid, title, rank, url, orcid, publ_list = self.reco_auth(self.auth[uuid], rerank=False)

            response = {
                "title": title,
                "rank": rank,
                "url": url,
                "orcid": orcid,
                "publ": self.remap_list(publ_list)
                }

        elif uuid in self.jour:
            uuid, title, rank, url, issn, publ_list = self.reco_jour(self.jour[uuid])

            response = {
                "title": title,
                "rank": rank,
                "url": url,
                "issn": issn,
                "publ": self.remap_list(publ_list)
                }

        elif uuid in self.topi:
            uuid, title, rank, publ_list = self.reco_topi(self.topi[uuid])

            response = {
                "title": title,
                "rank": rank,
                "publ": self.remap_list(publ_list)
                }

        return response


    def render_links (self):
        """
        leverage the `nxg` graph to generate HTML to render links for
        each entity in the knowledge graph
        """
        links = {}

        for p in self.prov.values():
            links[p.view["id"]] = self.render_prov(p)

        for d in self.data.values():
            links[d.view["id"]] = self.render_data(d)

        for a in self.auth.values():
            links[a.view["id"]] = self.render_auth(a)

        for j in self.jour.values():
            links[j.view["id"]] = self.render_jour(j)

        for t in self.topi.values():
            links[t.view["id"]] = self.render_topi(t)

        for p in self.publ.values():
            links[p.view["id"]] = self.render_publ(p)

        return links


    def download_links (self, uuid):
        """
        download links for the given dataset ID
        """
        dataset = self.data[uuid].view["title"]
        l = []

        for id, node in self.publ.items():
            if uuid in node.view["datasets"]:
                jour_uuid = node.view["journal"]

                if jour_uuid in self.jour:
                    jour_title = self.jour[jour_uuid].view["title"]
                else:
                    jour_title = ""

                l.append([
                        dataset,
                        node.view["title"],
                        jour_title,
                        node.view["doi"],
                        node.view["abstract"]
                        ])

        df = pd.DataFrame(l, columns=["dataset", "publication", "journal", "url", "abstract"])
        data_rows = df.to_csv()
        data_name = dataset.replace(" ", "")[:8].upper()

        return data_rows, data_name


    ######################################################################
    ## neighborhoods

    def get_subgraph (self, search_term, radius):
        """
        use BFS to label nodes as part of a 'neighborhood' subgraph
        """
        subgraph = set([])
        paths = {}
        the_node_id = None

        for node_id, label in self.labels.items():
            if label == search_term:
                the_node_id = node_id
                r = nx.bfs_edges(self.nxg, source=node_id, depth_limit=radius)
                subgraph = set([node_id])

                for _, neighbor in r:
                    subgraph.add(neighbor)

                paths = nx.single_source_shortest_path_length(self.nxg, node_id, cutoff=radius)
                break

        return subgraph, paths, str(the_node_id)


    def extract_neighborhood (self, radius, subgraph, paths, node_id, html_path):
        """
        extract the neighbor entities from the subgraph, while
        generating a network diagram
        """
        hood = RCNeighbors()
        g = Network(notebook=False, height="450px", width="100%")
        g.force_atlas_2based()

        for p in self.prov.values():
            if "used" in p.view:
                p_id = self.get_id(p.view["id"])
        
                if p_id in subgraph:
                    scale, impact = self.scale[p_id]
                    rank = (radius - paths[p_id], 0, 0.0, impact)
                    p.view["rank"] = rank
                    hood.prov.append([ p_id, rank, "{:.4f}".format(impact), p.view["title"], p.view["ror"], True ])

                    title = "{}<br/>rank: {:.4f}<br/>{}".format(p.view["title"], impact, p.view["ror"])
                    g.add_node(p_id, label=p.view["title"], title=title, color="orange", size=scale)

        for d in self.data.values():
            if "used" in d.view:
                d_id = self.get_id(d.view["id"])
        
                if d_id in subgraph:
                    p_id = self.get_id(d.view["provider"])
                    scale, impact = self.scale[d_id]
                    rank = (radius - paths[d_id], 0, 0.0, impact)
                    d.view["rank"] = rank
                    hood.data.append([ d_id, rank, "{:.4f}".format(impact), d.view["title"], self.labels[p_id], True ])

                    title = "{}<br/>rank: {:.4f}<br/>provider: {}".format(d.view["title"], impact, self.labels[p_id])
                    g.add_node(d_id, label=d.view["title"], title=title, color="red", size=scale)

                    if p_id in subgraph:
                        g.add_edge(d_id, p_id, color="gray")

        for a in self.auth.values():
            if "used" in a.view:
                a_id = self.get_id(a.view["id"])

                if a_id in subgraph:
                    if node_id in a.view["mle"]:
                        count, pt_est = a.view["mle"][node_id]
                    else:
                        count = 0
                        pt_est = 0.0

                    scale, impact = self.scale[a_id]
                    rank = (radius - paths[a_id], count, pt_est, impact)
                    a.view["rank"] = rank
                    hood.auth.append([ a_id, rank, "{:.4f}".format(impact), a.view["title"], a.view["orcid"], True ])

                    title = "{}<br/>rank: {:.4f}<br/>{}".format(a.view["title"], impact, a.view["orcid"])
                    g.add_node(a_id, label=a.view["title"], title=title, color="purple", size=scale)

        for t in self.topi.values():
            if "used" in t.view:
                t_id = self.get_id(t.view["id"])

                if t_id in subgraph:
                    if node_id in t.view["mle"]:
                        count, pt_est = t.view["mle"][node_id]
                    else:
                        count = 0
                        pt_est = 0.0

                    scale, impact = self.scale[t_id]
                    rank = (radius - paths[t_id], count, pt_est, impact)
                    t.view["rank"] = rank
                    hood.topi.append([ t_id, rank, "{:.4f}".format(impact), t.view["title"], None, True ])

                    title = "{}<br/>rank: {:.4f}".format(t.view["title"], impact)
                    g.add_node(t_id, label=t.view["title"], title=title, color="cyan", size=scale)

        for j in self.jour.values():
            if "used" in j.view:
                j_id = self.get_id(j.view["id"])

                if j_id in subgraph:
                    if j.view["title"] == "unknown":
                        shown = False
                    else:
                        shown = True

                    if node_id in j.view["mle"]:
                        count, pt_est = j.view["mle"][node_id]
                    else:
                        count = 0
                        pt_est = 0.0

                    scale, impact = self.scale[j_id]
                    rank = (radius - paths[j_id], count, pt_est, impact)
                    j.view["rank"] = rank
                    hood.jour.append([ j_id, rank, "{:.4f}".format(impact), j.view["title"], j.view["issn"], shown ])

                    title = "{}<br/>rank: {:.4f}<br/>{}".format(j.view["title"], impact, j.view["issn"])
                    g.add_node(j_id, label=j.view["title"], title=title, color="green", size=scale)

        for p in self.publ.values():
            p_id = self.get_id(p.view["id"])

            if p_id in subgraph:
                if len(p.view["title"]) >= self.MAX_TITLE_LEN:
                    abbrev_title = p.view["title"][:self.MAX_TITLE_LEN] + "..."
                else:
                    abbrev_title = p.view["title"]

                scale, impact = self.scale[p_id]
                rank = (radius - paths[p_id], 0, 0.0, impact)
                p.view["rank"] = rank
                hood.publ.append([ p_id, rank, "{:.4f}".format(impact), abbrev_title, p.view["doi"], True ])

                title = "{}<br/>rank: {:.4f}<br/>{}".format(p.view["title"], impact, p.view["doi"])
                g.add_node(p_id, label=p.view["title"], title=title, color="blue", size=scale)

                if p.view["journal"]:
                    j_id = self.get_id(p.view["journal"])

                    if j_id in subgraph:
                        g.add_edge(p_id, j_id, color="gray")

                for d in p.view["datasets"]:
                    d_id = self.get_id(d)
            
                    if d_id in subgraph:
                        g.add_edge(p_id, d_id, color="gray")

                for a in p.view["authors"]:
                    a_id = self.get_id(a)
            
                    if a_id in subgraph:
                        g.add_edge(p_id, a_id, color="gray")

                for t in p.view["topics"]:
                    t_id = self.get_id(t)
            
                    if t_id in subgraph:
                        g.add_edge(p_id, t_id, color="gray")

        #g.show_buttons()
        g.write_html(html_path, notebook=False)

        return hood


######################################################################

def main ():
    # build a graph from the JSON-LD corpus
    net = RCNetwork()
    net.parse_corpus(Path("full.jsonld"))

    # rank and scale each entity
    net.build_analytics_graph()
    net.scale_ranks()

    # constrain the graph
    t0 = time.time()

    search_term = "IRI Infoscan"
    radius = 2

    subgraph, paths, node_id = net.get_subgraph(search_term, radius)
    hood = net.extract_neighborhood(radius, subgraph, paths, node_id, "corpus.html")

    print(hood.serialize(t0))


if __name__ == "__main__":
    main()
