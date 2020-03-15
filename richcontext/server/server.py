#!/usr/bin/env python
# encoding: utf-8

from css_html_js_minify import html_minify
from jinja2 import Environment, FileSystemLoader
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
    MAX_TITLE_LEN = 60

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
            impact = percentileofscore(ranks, rank)
            scale = (((impact / num_quant) + 5) * scale_factor)
            self.scale[id] = [int(round(scale)), impact / 100.0]


    def load_network (self, path):
        """
        run the full usage pattern, prior to use of serialize() or
        subgraph()
        """
        t0 = time.time()

        self.parse_corpus(path)
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


    def render_links (self, template_folder):
        """
        leverage the `nxg` graph to generate HTML to render links for
        each entity in the knowledge graph
        """
        data_template = self.get_template(template_folder, "links/data.html")
        prov_template = self.get_template(template_folder, "links/prov.html")
        publ_template = self.get_template(template_folder, "links/publ.html")
        jour_template = self.get_template(template_folder, "links/jour.html")
        auth_template = self.get_template(template_folder, "links/auth.html")
        topi_template = self.get_template(template_folder, "links/topi.html")

        links = {}

        # providers
        for p in self.prov.values():
            p_id = self.get_id(p.view["id"])

            if not p_id in self.scale:
                continue

            scale, impact = self.scale[p_id]

            data_list = []
            edges = self.nxg[self.get_id(p.view["id"])]

            for neighbor, attr in edges.items():
                neighbor_scale, neighbor_impact = self.scale[neighbor]
                data_list.append([ neighbor, self.labels[neighbor], neighbor_impact ])

            if len(p.view["ror"]) < 1:
                ror = None
                url = None
            else:
                ror = p.view["ror"].replace("https://ror.org/", "")
                url = p.view["ror"]

            links[p.view["id"]] = self.render_template(
                prov_template, 
                uuid=p.view["id"],
                title=p.view["title"],
                rank="{:.4f}".format(impact),
                url=url,
                ror=ror,
                data_list=sorted(data_list, key=lambda x: x[2], reverse=True)
                )

        # datasets
        for d in self.data.values():
            d_id = self.get_id(d.view["id"])

            if not d_id in self.scale:
                continue

            p_id = self.get_id(d.view["provider"])
            scale, impact = self.scale[d_id]

            publ_list = []
            seen_set = set([ p_id ])
            edges = self.nxg[self.get_id(d.view["id"])]

            for neighbor, attr in edges.items():
                if neighbor not in seen_set:
                    neighbor_scale, neighbor_impact = self.scale[neighbor]
                    publ_list.append([ neighbor, self.labels[neighbor], neighbor_impact ])

            links[d.view["id"]] = self.render_template(
                data_template, 
                uuid=d.view["id"],
                title=d.view["title"],
                rank="{:.4f}".format(impact),
                url=d.view["url"],
                provider=(p_id, self.labels[p_id]),
                publ_list=sorted(publ_list, key=lambda x: x[2], reverse=True)
                )

        # authors
        for a in self.auth.values():
            a_id = self.get_id(a.view["id"])

            if not a_id in self.scale:
                continue

            scale, impact = self.scale[a_id]

            publ_list = []
            edges = self.nxg[self.get_id(a.view["id"])]

            for neighbor, attr in edges.items():
                neighbor_scale, neighbor_impact = self.scale[neighbor]
                publ_list.append([ neighbor, self.labels[neighbor], neighbor_scale ])

            if len(a.view["orcid"]) < 1:
                orcid = None
                url = None
            else:
                orcid = a.view["orcid"].replace("https://orcid.org/", "")
                url = a.view["orcid"]

            links[a.view["id"]] = self.render_template(
                auth_template, 
                uuid=a.view["id"],
                title=a.view["title"],
                rank="{:.4f}".format(impact),
                url=url,
                orcid=orcid,
                publ_list=sorted(publ_list, key=lambda x: x[2], reverse=True)
                )

        # journals
        for j in self.jour.values():
            j_id = self.get_id(j.view["id"])

            if not j_id in self.scale:
                continue

            scale, impact = self.scale[j_id]

            publ_list = []
            edges = self.nxg[self.get_id(j.view["id"])]

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

            links[j.view["id"]] = self.render_template(
                jour_template, 
                uuid=j.view["id"],
                title=j.view["title"],
                rank="{:.4f}".format(impact),
                url=url,
                issn=issn,
                publ_list=sorted(publ_list, key=lambda x: x[2], reverse=True)
                )

        # topics
        for t in self.topi.values():
            t_id = self.get_id(t.view["id"])

            if not t_id in self.scale:
                continue

            scale, impact = self.scale[t_id]

            publ_list = []
            edges = self.nxg[self.get_id(t.view["id"])]

            for neighbor, attr in edges.items():
                neighbor_scale, neighbor_impact = self.scale[neighbor]
                publ_list.append([ neighbor, self.labels[neighbor], neighbor_scale ])

            links[t.view["id"]] = self.render_template(
                topi_template, 
                uuid=t.view["id"],
                title=t.view["title"],
                rank="{:.4f}".format(impact),
                publ_list=sorted(publ_list, key=lambda x: x[2], reverse=True)
                )

        # publications
        for p in self.publ.values():
            p_id = self.get_id(p.view["id"])

            if not p_id in self.scale:
                continue

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

            links[p.view["id"]] = self.render_template(
                publ_template, 
                uuid=p.view["id"],
                title=p.view["title"],
                rank="{:.4f}".format(impact),
                url=url,
                doi=doi,
                pdf=p.view["pdf"],
                journal=journal,
                abstract=abstract,
                auth_list=auth_list,
                data_list=sorted(data_list, key=lambda x: x[2], reverse=True),
                topi_list=sorted(topi_list, key=lambda x: x[2], reverse=True)
                )

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

        for node_id, label in self.labels.items():
            if label == search_term:
                r = nx.bfs_edges(self.nxg, source=node_id, depth_limit=radius)
                subgraph = set([node_id])

                for _, neighbor in r:
                    subgraph.add(neighbor)

                paths = nx.single_source_shortest_path_length(self.nxg, node_id, cutoff=radius)
                break

        return subgraph, paths


    def extract_neighborhood (self, subgraph, paths, search_term, html_path):
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
                    hood.prov.append([ p_id, "{:.4f}".format(impact), p.view["title"], p.view["ror"], True ])

                    title = "{}<br/>rank: {:.4f}<br/>{}".format(p.view["title"], impact, p.view["ror"])
                    g.add_node(p_id, label=p.view["title"], title=title, color="orange", size=scale)

        for d in self.data.values():
            if "used" in d.view:
                d_id = self.get_id(d.view["id"])
        
                if d_id in subgraph:
                    p_id = self.get_id(d.view["provider"])
                    scale, impact = self.scale[d_id]
                    hood.data.append([ d_id, "{:.4f}".format(impact), d.view["title"], self.labels[p_id], True ])

                    title = "{}<br/>rank: {:.4f}<br/>provider: {}".format(d.view["title"], impact, self.labels[p_id])
                    g.add_node(d_id, label=d.view["title"], title=title, color="red", size=scale)

                    if p_id in subgraph:
                        g.add_edge(d_id, p_id, color="gray")

        for a in self.auth.values():
            if "used" in a.view:
                a_id = self.get_id(a.view["id"])

                if a_id in subgraph:
                    scale, impact = self.scale[a_id]
                    hood.auth.append([ a_id, "{:.4f}".format(impact), a.view["title"], a.view["orcid"], True ])

                    title = "{}<br/>rank: {:.4f}<br/>{}".format(a.view["title"], impact, a.view["orcid"])
                    g.add_node(a_id, label=a.view["title"], title=title, color="purple", size=scale)

        for t in self.topi.values():
            if "used" in t.view:
                t_id = self.get_id(t.view["id"])

                if t_id in subgraph:
                    scale, impact = self.scale[t_id]
                    hood.topi.append([ t_id, "{:.4f}".format(impact), t.view["title"], None, True ])

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

                    scale, impact = self.scale[j_id]
                    hood.jour.append([ j_id, "{:.4f}".format(impact), j.view["title"], j.view["issn"], shown ])

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
                hood.publ.append([ p_id, "{:.4f}".format(impact), abbrev_title, p.view["doi"], True ])

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

    subgraph, paths = net.get_subgraph(search_term=search_term, radius=radius)
    hood = net.extract_neighborhood(subgraph, paths, search_term, "corpus.html")

    print(hood.serialize(t0))


if __name__ == "__main__":
    main()
