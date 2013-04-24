"""
output classes for database graphs
"""

__versoin__ = "0.1.0"
__author__ = "David Poisl <david@poisl.at>"


from xml.etree import ElementTree
import json


COLUMN_TEMPLATE_NOINFO = "%(name)s - %(translated_type)s"
COLUMN_TEMPLATE_NULLABLE_STRING = "NULL"
COLUMN_TEMPLATE_NOTNULLABLE_STRING = "NOT NULL"
COLUMN_TEMPLATE_INFO = COLUMN_TEMPLATE_NOINFO + " [%(info)s]"
COLUMN_TEMPLATE_DEFAULT_STRING = "DEFAULT=%(default)s"
COLUMN_TEMPLATE_NODEFAULT_STRING = None


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
    # TODO: TEMPLATES!
    def _create_empty_document(self):
        attributes = {"xmlns": "http://graphml.graphdrawing.org/xmlns",
                      "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance", 
                      "xmlns:y": "http://www.yworks.com/xml/graphml",
                      "xmlns:yed": "http://www.yworks.com/xml/yed/3",
                      "xsi:schemaLocation": "http://graphml.graphdrawing.org/xmlns "
                         "http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd"
                      }
        root = ElementTree.Element("graphml", attributes)
        root.append(root.makeelement("key", {"id": "nodegraphics", "for": "node", 
                                             "yfiles.type": "nodegraphics"}))
        root.append(root.makeelement("key", {"id": "edgegraphics", "for": "edge", 
                                             "yfiles.type": "edgegraphics"}))
        root.append(root.makeelement("key", {"id": "nodeurl", "for": "node", 
                                             "attr.name": "url", 
                                             "attr.type": "string"}))
        root.append(root.makeelement("key", {"id": "nodedescription", "for": "node",
                                             "attr.name": "description", 
                                             "attr.type": "string"}))
        root.append(root.makeelement("key", {"id": "edgeurl", "for": "edge", 
                                             "attr.name": "url", 
                                             "attr.type": "string"}))
        root.append(root.makeelement("key", {"id": "edgedescription", "for": "edge",
                                             "attr.name": "description", 
                                             "attr.type": "string"}))
        root.append(root.makeelement("graph", {"edgedefault": "directed", 
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
        TABLE_TITLE_TEMPLATE = "%(name)s"
        TABLE_DESCRIPTION_TEMPLATE = "%(description)s"
        SCHEMA_DESCRIPTION_TEMPLATE = "%(description)s"
        SCHEMA_LABEL_TEMPLATE = "%(name)s"

        document = self._create_empty_document()
        graph = document.find("graph")
        for (schema_name, schema_data) in data["schemas"].items():
            schema_node = graph.makeelement("node", {"id": "schema-%s-node" % schema_name})
            graph.append(schema_node)
            
            schema_description = graph.makeelement("data", {"key": "nodedescription"})
            schema_description.text = SCHEMA_DESCRIPTION_TEMPLATE % schema_data
            schema_node.append(schema_description)
            
            self._add_schema_label(schema_node, SCHEMA_LABEL_TEMPLATE % schema_data)
            schema_graph = graph.makeelement("graph", {"id": "schema-%s-graph" % schema_name})
            schema_node.append(schema_graph)

            for (table_name, table_data) in schema_data["tables"].items():
                # get text for table nodes
                (attribute_text, lines) = self._table_description(table_data)
                # create table node!
                node = graph.makeelement("node", {"id": "table-%s-%s" % (schema_name, table_name)})
                schema_graph.append(node)

                node_description = graph.makeelement("data", {"key": "nodedescription"})
                node_description.text = TABLE_DESCRIPTION_TEMPLATE % table_data
                node.append(node_description)

                node_data = graph.makeelement("data", {"key": "nodegraphics"})
                node.append(node_data)
                gn = graph.makeelement("y:GenericNode", 
                        {"configuration": "com.yworks.entityRelationship.big_entity",
                            })
                node_data.append(gn)
                gn.append(graph.makeelement("y:Geometry", {"height": str(lines * 13 + 70),
                                                           "width": "500", 
                                                           "x": "0", "y": "0"}))
                
                label = graph.makeelement("y:NodeLabel", {"alignment": "center",
                    "autoSizePolicy": "content",
                    "configuration": "com.yworks.entityRelationship.label.name",
                    "modelName": "internal",
                    "modelPosition": "t"})
                label.text = table_name
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
        COLUMN_TEMPLATE = "%(name)s - %(type)s"
        INFO_TEMPLATE = "[%s]"
        INFO_LABELS = {"nullable": "NULL", "default": "DEFAULT=%(default)s"}

        columns = table["columns"]
        constraints = table["constraints"]
        text = []
        for column in columns:
            info = []
            if column["nullable"]:
                info.append(INFO_LABELS["nullable"])
            if column["default"]:
                info.append(INFO_LABELS["default"] % {"default": column["default"]})
            col_text = COLUMN_TEMPLATE % column
            if len(info):
                col_text += INFO_TEMPLATE % (", ".join(info))
            text.append(col_text)
        return ("\n".join(text), len(text) + 1)

    def _generate_foreign_keys(self, graph, data):
        FKEY_LABEL_TEMPLATE = ("%(constraint_schema)s.%(constraint_name)s\n"
                "From: %(src_schema)s.%(src_table)s (%(src_column)s)\n"
                "To: %(dst_schema)s.%(dst_table)s %(dst_column)s)\n"
                "Indexed: %(src_indexed)s\nNullable: %(src_nullable)s")
        for fkey in data["foreign_keys"]:
            src_label = "table-%s-%s" % (fkey["src_schema"], fkey["src_table"])
            dst_label = "table-%s-%s" % (fkey["dst_schema"], fkey["dst_table"])
            label = fkey["constraint_schema"] + "." + fkey["constraint_name"]
            description = FKEY_LABEL_TEMPLATE % fkey
            self._add_edge(graph, src_label, dst_label, label, description=description)


if __name__ == "__main__":
    import reader
    r = reader.Json("test.json")
    r = reader.PostgreSQL(host="db-test.intern.ewave.at", database="backoffice",
                          user="ewave", password="ewave")
    writer = Json(r, "test.json")
    writer2 = YEd(r, "test.graphml")
    writer()
    writer2()
