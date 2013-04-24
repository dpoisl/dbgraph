"""
output classes for database graphs
"""

__versoin__ = "0.1.0"
__author__ = "David Poisl <david@poisl.at>"


from xml.etree import ElementTree
import json


class Generic(object):
    def __init__(self, reader, filename):
        self.reader = reader
        self.filename = filename

    def __call__(self):
        data = self.reader.get_db_information()
        self.write(data)

    def write(self, data):
        raise NotImplementedError()


class Json(Generic):
    def write(self, data):
        with open(self.filename, "w") as file_:
            json.dump(data, file_)


class YEd(Generic):
    TABLE_lABEL_TEMPLATE = "%(name)s"
    TABLE_DESCRIPTION_TEMPLATE = "%(description)s"
    SCHEMA_DESCRIPTION_TEMPLATE = "%(description)s"
    SCHEMA_LABEL_TEMPLATE = "%(name)s"
    COLUMN_TEMPLATE = "%(name)s - %(type)s"
    INFO_TEMPLATE = "[%s]"
    INFO_LABELS = {"nullable": "NULL", "default": "DEFAULT=%(default)s"}
    FKEY_LABEL_TEMPLATE = ("%(constraint_schema)s.%(constraint_name)s\n"
            "From: %(src_schema)s.%(src_table)s (%(src_column)s)\n"
            "To: %(dst_schema)s.%(dst_table)s %(dst_column)s)\n"
            "Indexed: %(src_indexed)s\nNullable: %(src_nullable)s")

    def _element(node, name, attributes):
        node.append(node.makeelement(name, attributes))

    def _create_empty_document(self):
        attr = {"xmlns": "http://graphml.graphdrawing.org/xmlns",
                "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance", 
                "xmlns:y": "http://www.yworks.com/xml/graphml",
                "xmlns:yed": "http://www.yworks.com/xml/yed/3",
                "xsi:schemaLocation": "http://graphml.graphdrawing.org/xmlns "
                   "http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd"
                }
        root = ElementTree.Element("graphml", attr)
        self._element(root, "key", {"id": "nodegraphics", "for": "node", 
                                    "yfiles.type": "nodegraphics"}))
        self._element(root, "key", {"id": "edgegraphics", "for": "edge", 
                                    "yfiles.type": "edgegraphics"}))
        self._element(root, "key", {"id": "nodeurl", "for": "node", 
                                    "attr.name": "url", 
                                    "attr.type": "string"}))
        self._element(root, "key", {"id": "nodedescription", "for": "node",
                                    "attr.name": "description", 
                                    "attr.type": "string"}))
        self._element(root, "key", {"id": "edgeurl", "for": "edge", 
                                    "attr.name": "url", 
                                    "attr.type": "string"}))
        self._element(root, "key", {"id": "edgedescription", "for": "edge",
                                    "attr.name": "description", 
                                    "attr.type": "string"}))
        self._element(root, "graph", {"edgedefault": "directed", 
                                      "id": "database"}))
        return root

    def _add_schema_label(self, node, label):
        graphics = node.makeelement("data", {"key": "nodegraphics"})
        node.append(graphics)
        group = node.makeelement("y:GroupNode", {})
        graphics.append(group)
        label_node = node.makeelement("y:NodeLabel", {"autoSizePolicy": "content",
                                                      "modelName": "internal",
                                                      "modelPosition": "t"})
        label_node.text = label
        group.append(label_node)

    def _generate_document(self, data):
        document = self._create_empty_document()
        graph = document.find("graph")

        for (schema_name, schema_data) in data["schemas"].items():
            schema_node = graph.makeelement("node", {"id": "schema-%s-node" % schema_name})
            graph.append(schema_node)
            
            schema_description = graph.makeelement("data", {"key": "nodedescription"})
            schema_description.text = self.SCHEMA_DESCRIPTION_TEMPLATE % schema_data
            schema_node.append(schema_description)
            
            self._add_schema_label(schema_node, self.SCHEMA_LABEL_TEMPLATE % schema_data)
            schema_graph = graph.makeelement("graph", {"id": "schema-%s-graph" % schema_name})
            schema_node.append(schema_graph)

            for (table_name, table_data) in schema_data["tables"].items():
                # get text for table nodes
                (attribute_text, line_count) = self._table_description(table_data)
                # create table node!
                node = graph.makeelement("node", {"id": "table-%s-%s" % (
                                                  schema_name, table_name)})
                schema_graph.append(node)

                node_description = graph.makeelement("data", {"key": "nodedescription"})
                node_description.text = self.TABLE_DESCRIPTION_TEMPLATE % table_data
                node.append(node_description)

                node_data = graph.makeelement("data", {"key": "nodegraphics"})
                node.append(node_data)
                gn = graph.makeelement("y:GenericNode", 
                        {"configuration": "com.yworks.entityRelationship.big_entity"})
                node_data.append(gn)
                gn.append(graph.makeelement("y:Geometry", {"height": str(line_count * 13 + 70),
                                                           "width": "500", 
                                                           "x": "0", "y": "0"}))
                
                label = graph.makeelement("y:NodeLabel", {"alignment": "center",
                    "autoSizePolicy": "content",
                    "configuration": "com.yworks.entityRelationship.label.name",
                    "modelName": "internal",
                    "modelPosition": "t"})
                label.text = self.TABLE_LABEL_TEMPLATE % table_data
                gn.append(label)
                
                label = graph.makeelement("y:NodeLabel", {"alignment": "left", 
                    "autoSizePolicy": "content",
                    "configuration": "com.yworks.entityRelationship.label.attributes", 
                    "modelPosition": "bl"})
                label.text = attribute_text
                gn.append(label)
        self._generate_foreign_keys(graph, data)
        return document

    def _add_edge(self, graph, source, target, label, description=None, url=None):
        edge = graph.makeelement("edge", {"id": "%s::%s" % (source, target), 
                                          "source": source, "target": target})
        graph.append(edge)
        if url is not None:
            url_node = graph.makeelement("data", {"key": "edgeurl"})
            url_node.text = url
            edge.append(url_node)
        if description is not None:
            description_node = graph.makeelement("data", {"key": "edgedescription"})
            description_node.text = description
            edge.append(description_node)
        edgegraphics = graph.makeelement("data", {"key": "edgegraphics"})
        edge.append(edgegraphics)
        polyline = graph.makeelement("y:PolyLineEdge", {})
        edgegraphics.append(polyline)
        edgelabel = graph.makeelement("y:EdgeLabel", {})
        edgelabel.text = label
        polyline.append(edgelabel)
        polyline.append(graph.makeelement("y:Arrows", {"source": "none", 
                                                       "target": "standard"}))

    def write(self, data):
        document = self._generate_document(data)
        tree = ElementTree.ElementTree(document)
        with open(self.filename, "w") as file_:
            tree.write(file_, "UTF-8", True)

    def _table_description(self, table, process_constraints=False):
        columns = table["columns"]
        constraints = table["constraints"]
        text = []
        for column in columns:
            info = []
            if column["nullable"]:
                info.append(self.INFO_LABELS["nullable"])
            if column["default"]:
                info.append(INFO_LABELS["default"] % {"default": column["default"]})
            col_text = self.COLUMN_TEMPLATE % column
            if len(info):
                col_text += self.INFO_TEMPLATE % (", ".join(info))
            text.append(col_text)
        return ("\n".join(text), len(text) + 1)

    def _generate_foreign_keys(self, graph, data):
        for fkey in data["foreign_keys"]:
            src_label = "table-%s-%s" % (fkey["src_schema"], fkey["src_table"])
            dst_label = "table-%s-%s" % (fkey["dst_schema"], fkey["dst_table"])
            label = fkey["constraint_schema"] + "." + fkey["constraint_name"]
            description = self.FKEY_LABEL_TEMPLATE % fkey
            self._add_edge(graph, src_label, dst_label, label, description=description)


class Dot(Generic):
    pass #TODO: everything!

if __name__ == "__main__":
    import reader
    r = reader.Json("test.json")
#    r = reader.PostgreSQL(host="db-test.intern.ewave.at", database="backoffice",
#                          user="ewave", password="ewave")
#    writer = Json(r, "test.json")
    writer2 = YEd(r, "test.graphml")
    writer()
    writer2()
